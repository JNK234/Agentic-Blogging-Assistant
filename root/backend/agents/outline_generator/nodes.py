import logging
import json
import re
from typing import Dict, List, Any

from langchain_core.exceptions import OutputParserException
from backend.utils.file_parser import ParsedContent
from backend.agents.outline_generator.state import OutlineState
from backend.agents.outline_generator.prompts import PROMPT_CONFIGS
from backend.services.persona_service import PersonaService
from backend.agents.cost_tracking_decorator import track_node_costs
from backend.services.sql_project_manager import MilestoneType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_json_response(response: str) -> str:
    """Clean LLM response by removing markdown fences and extra content."""
    if not response:
        return response
    
    # Remove markdown code fences
    response = response.strip()
    
    # Try to extract JSON from markdown code blocks
    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(json_pattern, response, re.DOTALL)
    if match:
        response = match.group(1).strip()
        logging.info("Removed markdown fences from JSON response")
    
    return response

async def safe_parse_with_retry(parser, model, prompt, operation_name: str, max_retries: int = 2):
    """Safely parse LLM response with retry logic for failed parsing."""
    for attempt in range(max_retries + 1):
        try:
            # Get LLM response
            response = await model.ainvoke(prompt)
            
            if not isinstance(response, str) and response:
                response = response.content
            
            logging.info(f"{operation_name} response (attempt {attempt + 1}): {response[:200]}...")
            
            # First attempt: clean and parse
            cleaned_response = clean_json_response(response)
            return parser.parse(cleaned_response)
        
        except OutputParserException as e:
            logging.warning(f"Parsing failed for {operation_name} (attempt {attempt + 1}): {e}")
            
            if attempt < max_retries:
                logging.info(f"Retrying {operation_name} (attempt {attempt + 2}/{max_retries + 1})")
                continue
            
            # Final attempt: try parsing original response
            try:
                return parser.parse(response)
            except OutputParserException as e2:
                logging.error(f"All parsing attempts failed for {operation_name}")
                logging.error(f"Final response: {response[:500]}...")
                logging.error(f"Cleaned response: {cleaned_response[:500]}...")
                raise Exception(f"JSON parsing failed for {operation_name} after {max_retries + 1} attempts. LLM response may be malformed: {str(e2)}")
        
        except Exception as e:
            logging.error(f"Unexpected error during {operation_name} (attempt {attempt + 1}): {e}")
            if attempt == max_retries:
                logging.error(f"Response content: {response[:500]}...")
                raise

def safe_parse_with_fallback(parser, response: str, operation_name: str):
    """Safely parse LLM response with fallback handling (for backward compatibility)."""
    try:
        # Validate response is not null or empty
        if response is None:
            logging.error(f"LLM returned null response for {operation_name}")
            raise Exception(f"LLM returned null response for {operation_name}. Check prompt and model configuration.")
        
        if not response or not response.strip():
            logging.error(f"LLM returned empty response for {operation_name}")
            raise Exception(f"LLM returned empty response for {operation_name}. Check prompt content and model configuration.")
        
        logging.info(f"Processing {operation_name} response: {response[:200]}...")
        
        # First attempt: clean and parse
        cleaned_response = clean_json_response(response)
        return parser.parse(cleaned_response)
    
    except OutputParserException as e:
        logging.warning(f"Initial parsing failed for {operation_name}: {e}")
        
        # Second attempt: try parsing original response
        try:
            return parser.parse(response)
        except OutputParserException as e2:
            logging.error(f"Both parsing attempts failed for {operation_name}")
            logging.error(f"Original response: {response[:500]}...")
            logging.error(f"Cleaned response: {cleaned_response[:500] if 'cleaned_response' in locals() else 'N/A'}...")
            raise Exception(f"JSON parsing failed for {operation_name}. LLM response may be malformed: {str(e2)}")
    
    except Exception as e:
        logging.error(f"Unexpected error during {operation_name} parsing: {e}")
        logging.error(f"Response content: {response[:500] if response else 'None'}...")
        raise

@track_node_costs("analyze_content", agent_name="OutlineGeneratorAgent", stage="outline_generation")
async def analyze_content(state: OutlineState) -> OutlineState:
    """Analyzes the content using LLM to extract key information."""
    logging.info("Executing node: analyze_content")
    try:
        # Extract section headers from markdown metadata if available
        markdown_section_headers = "No section headers available"
        if (state.markdown_content and 
            hasattr(state.markdown_content, 'metadata') and 
            state.markdown_content.metadata and
            'section_headers' in state.markdown_content.metadata):

            headers = json.loads(state.markdown_content.metadata['section_headers'])
            # Format the headers for display
            header_lines = []
            for header in headers:
                level = header.get('level', 1)
                text = header.get('text', '')
                indentation = '  ' * (level - 1)  # Indent based on header level
                header_lines.append(f"{indentation}{'#' * level} {text}")

            markdown_section_headers = "\n".join(header_lines)
            logging.info(f"Found section headers in markdown: {markdown_section_headers}")
        
        # Prepare input variables for the prompt
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["content_analysis"]["parser"].get_format_instructions(),
            "notebook_content_main_content": state.notebook_content.main_content if state.notebook_content else "",
            "notebook_content_code_segments": str(state.notebook_content.code_segments if state.notebook_content else []),
            "markdown_content_main_content": state.markdown_content.main_content if state.markdown_content else "",
            "markdown_content_code_segments": str(state.markdown_content.code_segments if state.markdown_content else []),
            "notebook_content_metadata": str(state.notebook_content.metadata if state.notebook_content else {}),
            "markdown_content_metadata": str(state.markdown_content.metadata if state.markdown_content else {}),
            "markdown_section_headers": markdown_section_headers
        }

        # Get the prompt and format it
        prompt = PROMPT_CONFIGS["content_analysis"]["prompt"].format(**input_variables)
        
        # Parse the response with retry logic for critical content analysis
        state.analysis_result = await safe_parse_with_retry(
            PROMPT_CONFIGS["content_analysis"]["parser"],
            state.model,
            prompt,
            "content_analysis",
            max_retries=2
        )
        logging.info("Content analysis completed successfully")
        
    except Exception as e:
        logging.error(f"Error in analyze_content: {str(e)}")
        raise
    
    return state

@track_node_costs("difficulty_assessor", agent_name="OutlineGeneratorAgent", stage="outline_generation")
async def difficulty_assessor(state: OutlineState) -> OutlineState:
    """Assesses the difficulty level of the content."""
    logging.info("Executing node: difficulty_assessor")
    try:
        # Prepare input variables
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["difficulty_assessment"]["parser"].get_format_instructions(),
            "technical_concepts": str(state.analysis_result.technical_concepts),
            "complexity_indicators": str(state.analysis_result.complexity_indicators)
        }

        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["difficulty_assessment"]["prompt"].format(**input_variables)
        response = await state.model.ainvoke(prompt)
        
        if not isinstance(response, str):
            # Extract JSON file 
            response = response.content            
        
        print(f"Difficulty Assessment Response: {response}\n\n\n")
        
        # Parse and update state with fallback handling
        state.difficulty_level = safe_parse_with_fallback(
            PROMPT_CONFIGS["difficulty_assessment"]["parser"], 
            response, 
            "difficulty_assessment"
        )
        logging.info(f"Difficulty assessment completed: {state.difficulty_level.level}")
        
    except Exception as e:
        logging.error(f"Error in difficulty_assessor: {str(e)}")
        raise
    
    return state

@track_node_costs("prerequisite_identifier", agent_name="OutlineGeneratorAgent", stage="outline_generation")
async def prerequisite_identifier(state: OutlineState) -> OutlineState:
    """Identifies prerequisites needed to understand the content."""
    logging.info("Executing node: prerequisite_identifier")
    try:
        # Check if content has actual code - if not, skip tools/setup requirements
        has_code = state.analysis_result.has_actual_code if state.analysis_result else False
        content_type = state.analysis_result.content_type if state.analysis_result else "theoretical"
        
        logging.info(f"Content analysis: has_actual_code={has_code}, content_type={content_type}")
        
        if not has_code and content_type == "theoretical":
            # For theoretical content, only include knowledge prerequisites
            from backend.agents.outline_generator.state import Prerequisites
            state.prerequisites = Prerequisites(
                required_knowledge=state.analysis_result.technical_concepts[:3] if state.analysis_result else [],
                recommended_tools=[],  # No tools needed for theoretical content
                setup_instructions=[]  # No setup needed for theoretical content
            )
            logging.info("Skipped tools/setup for theoretical content - only added knowledge prerequisites")
            return state
        
        # For practical/mixed content, proceed with full prerequisite analysis
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["prerequisites"]["parser"].get_format_instructions(),
            "technical_concepts": str(state.analysis_result.technical_concepts),
            "learning_objectives": str(state.analysis_result.learning_objectives)
        }

        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["prerequisites"]["prompt"].format(**input_variables)
        response = await state.model.ainvoke(prompt)
        
        if not isinstance(response, str):
            # Extract JSON file 
            response = response.content
            
        logging.info(f"Prerquisite Identifier: {response}\n\n\n")
        
        # Parse and update state with fallback handling
        state.prerequisites = safe_parse_with_fallback(
            PROMPT_CONFIGS["prerequisites"]["parser"], 
            response, 
            "prerequisites"
        )
        logging.info("Prerequisites identification completed")
        
    except Exception as e:
        logging.error(f"Error in prerequisite_identifier: {str(e)}")
        raise
    
    return state

@track_node_costs("outline_structurer", agent_name="OutlineGeneratorAgent", stage="outline_generation")
async def outline_structurer(state: OutlineState) -> OutlineState:
    """Structures the outline based on analysis and prerequisites."""
    logging.info("Executing node: outline_structurer")
    try:
        # Enhanced debugging logging
        logging.info(f"State analysis_result: {state.analysis_result is not None}")
        logging.info(f"State difficulty_level: {state.difficulty_level is not None}")
        logging.info(f"State prerequisites: {state.prerequisites is not None}")
        logging.info(f"State user_guidelines: {state.user_guidelines}")
        
        if state.analysis_result:
            logging.info(f"Analysis result main_topics: {len(state.analysis_result.main_topics) if state.analysis_result.main_topics else 0}")
            logging.info(f"Analysis result has_actual_code: {state.analysis_result.has_actual_code}")
            logging.info(f"Analysis result content_type: {state.analysis_result.content_type}")
        # Prepare input variables
        section_structure = "[]"
        if state.analysis_result and hasattr(state.analysis_result, 'section_structure'):
            section_structure = json.dumps(state.analysis_result.section_structure)
        
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["outline_structure"]["parser"].get_format_instructions(),
            "main_topics": str(state.analysis_result.main_topics) if state.analysis_result else "[]",
            "section_structure": section_structure,
            "difficulty_level": state.difficulty_level.level if state.difficulty_level else "",
            "prerequisites": {
                "required_knowledge": state.prerequisites.required_knowledge if state.prerequisites else [],
                "recommended_tools": state.prerequisites.recommended_tools if state.prerequisites else [],
                "setup_instructions": state.prerequisites.setup_instructions if state.prerequisites else []
            },
            "user_guidelines": state.user_guidelines if state.user_guidelines else "No specific guidelines provided.",
            "technical_concepts": str(state.analysis_result.technical_concepts) if state.analysis_result else "[]",
            "has_actual_code": state.analysis_result.has_actual_code if state.analysis_result else False,
            "content_type": state.analysis_result.content_type if state.analysis_result else "theoretical"
        }

        # Enhanced debugging for input variables
        logging.info(f"Input variables keys: {list(input_variables.keys())}")
        logging.info(f"Prerequisites structure: {input_variables['prerequisites']}")
        logging.info(f"User guidelines length: {len(input_variables['user_guidelines']) if input_variables['user_guidelines'] else 0}")

        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["outline_structure"]["prompt"].format(**input_variables)
        logging.info(f"Formatted prompt length: {len(prompt)} characters")
        
        response = await state.model.ainvoke(prompt)
        logging.info(f"LLM response type: {type(response)}")
        
        if not isinstance(response, str):
            # Extract JSON file 
            response = response.content
        
        logging.info(f"Outline Structure: {response}\n\n\n")
        
        # Parse and update state with fallback handling
        state.outline_structure = safe_parse_with_fallback(
            PROMPT_CONFIGS["outline_structure"]["parser"], 
            response, 
            "outline_structure"
        )
        logging.info("Outline structure completed")
        
    except Exception as e:
        logging.error(f"Error in outline_structurer: {str(e)}")
        raise
    
    return state

def _calculate_intelligent_length(state: OutlineState) -> int:
    """Calculate intelligent blog length based on content analysis and user preferences."""
    # Start with AI-suggested length from content analysis
    base_length = getattr(state.analysis_result, 'suggested_blog_length', 1500) if state.analysis_result else 1500
    
    # Override with custom length if specified
    if state.length_preference == "Custom" and state.custom_length:
        return state.custom_length
    
    # Apply user length preference if specified
    if state.length_preference and state.length_preference != "Auto-detect (Recommended)":
        if state.length_preference == "Short (800-1200)":
            base_length = min(base_length, 1200)
            base_length = max(base_length, 800)
        elif state.length_preference == "Medium (1200-2000)":
            base_length = min(base_length, 2000)
            base_length = max(base_length, 1200)
        elif state.length_preference == "Long (2000-3000)":
            base_length = min(base_length, 3000)
            base_length = max(base_length, 2000)
        elif state.length_preference == "Very Long (3000+)":
            base_length = max(base_length, 3000)
    
    # Adjust based on writing style
    if state.writing_style == "Concise & Focused":
        base_length = int(base_length * 0.8)  # 20% shorter
    elif state.writing_style == "Comprehensive & Detailed":
        base_length = int(base_length * 1.2)  # 20% longer
    # "Balanced" style uses base length as-is
    
    # Ensure reasonable bounds
    base_length = max(base_length, 500)   # Minimum 500 words
    base_length = min(base_length, 5000)  # Maximum 5000 words
    
    logging.info(f"Calculated intelligent blog length: {base_length} words "
                f"(preference: {state.length_preference}, style: {state.writing_style})")
    
    return base_length

@track_node_costs("final_generator", agent_name="OutlineGeneratorAgent", stage="outline_generation")
async def final_generator(state: OutlineState) -> OutlineState:
    """Generates the final outline in markdown format."""
    logging.info("Executing node: final_generator")
    try:
        # Initialize persona service and get persona from state
        persona_service = PersonaService()
        persona_name = getattr(state, 'persona', 'neuraforge')
        persona_instructions = persona_service.get_persona_prompt(persona_name)
        logger.info(f"Using persona: {persona_name} for outline generation")
        
        # Calculate intelligent target length based on content analysis and user preferences
        intelligent_length = _calculate_intelligent_length(state)
        
        # Prepare input variables
        input_variables = {
            "persona_instructions": persona_instructions,
            "format_instructions": PROMPT_CONFIGS["final_generation"]["parser"].get_format_instructions(),
            "title": state.outline_structure.title if state.outline_structure else "",
            "difficulty_level": state.difficulty_level.level if state.difficulty_level else "",
            "prerequisites": {
                "required_knowledge": state.prerequisites.required_knowledge,
                "recommended_tools": state.prerequisites.recommended_tools,
                "setup_instructions": state.prerequisites.setup_instructions
            } if state.prerequisites else {},
            "outline_structure": {
                "title": state.outline_structure.title,
                "sections": [
                    {
                        "title": section.title,
                        "subsections": section.subsections,
                        "learning_goals": section.learning_goals,
                        "estimated_time": section.estimated_time
                    } for section in state.outline_structure.sections
                ],
                "introduction": state.outline_structure.introduction,
                "conclusion": state.outline_structure.conclusion
            } if state.outline_structure else {}
        }

        # Format prompt and parse with retry logic for critical final generation
        prompt = PROMPT_CONFIGS["final_generation"]["prompt"].format(**input_variables)
        
        # Parse the response into FinalOutline format with retry logic
        parsed_outline = await safe_parse_with_retry(
            PROMPT_CONFIGS["final_generation"]["parser"],
            state.model,
            prompt,
            "final_generation",
            max_retries=2
        )
        
        # Store the final outline
        state.final_outline = parsed_outline
        logging.info("Final outline generation completed")

        # NEW: Save milestone to SQL if sql_project_manager is available
        if hasattr(state, 'sql_project_manager') and state.sql_project_manager and hasattr(state, 'project_id') and state.project_id:
            try:
                milestone_data = {
                    "title": parsed_outline.title if parsed_outline else "",
                    "difficulty": state.difficulty_level.level if state.difficulty_level else "",
                    "prerequisites": {
                        "required_knowledge": state.prerequisites.required_knowledge if state.prerequisites else [],
                        "recommended_tools": state.prerequisites.recommended_tools if state.prerequisites else [],
                        "setup_instructions": state.prerequisites.setup_instructions if state.prerequisites else ""
                    },
                    "sections": [
                        {
                            "title": section.title,
                            "subsections": section.subsections,
                            "learning_goals": section.learning_goals,
                            "estimated_time": section.estimated_time
                        } for section in (parsed_outline.sections if parsed_outline else [])
                    ]
                }
                await state.sql_project_manager.save_milestone(
                    project_id=state.project_id,
                    milestone_type=MilestoneType.OUTLINE_GENERATED,
                    data=milestone_data
                )
                logging.info(f"Saved OUTLINE_GENERATED milestone for project {state.project_id}")
            except Exception as e:
                logging.error(f"Failed to save outline milestone: {e}")
                # Don't fail the workflow for SQL errors

    except Exception as e:
        logging.error(f"Error in final_generator: {str(e)}")
        raise

    return state
