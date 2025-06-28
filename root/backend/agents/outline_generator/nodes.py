import logging
import json
from typing import Dict, List, Any

from root.backend.utils.file_parser import ParsedContent
from root.backend.agents.outline_generator.state import OutlineState
from root.backend.agents.outline_generator.prompts import PROMPT_CONFIGS
from root.backend.services.persona_service import PersonaService

logging.basicConfig(level=logging.INFO)

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
                
        # Get LLM response
        response = await state.model.ainvoke(prompt)
        
        if not isinstance(response, str) and response:
            # Extract JSON file 
            response = response.content
        
        print(f"Content Analysis Response: {response}\n\n\n")
        
        # Parse the response
        state.analysis_result = PROMPT_CONFIGS["content_analysis"]["parser"].parse(response)
        logging.info("Content analysis completed successfully")
        
    except Exception as e:
        logging.error(f"Error in analyze_content: {str(e)}")
        raise
    
    return state

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
        
        # Parse and update state
        state.difficulty_level = PROMPT_CONFIGS["difficulty_assessment"]["parser"].parse(response)
        logging.info(f"Difficulty assessment completed: {state.difficulty_level.level}")
        
    except Exception as e:
        logging.error(f"Error in difficulty_assessor: {str(e)}")
        raise
    
    return state

async def prerequisite_identifier(state: OutlineState) -> OutlineState:
    """Identifies prerequisites needed to understand the content."""
    logging.info("Executing node: prerequisite_identifier")
    try:
        # Prepare input variables
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
        
        # Parse and update state
        state.prerequisites = PROMPT_CONFIGS["prerequisites"]["parser"].parse(response)
        logging.info("Prerequisites identification completed")
        
    except Exception as e:
        logging.error(f"Error in prerequisite_identifier: {str(e)}")
        raise
    
    return state

async def outline_structurer(state: OutlineState) -> OutlineState:
    """Structures the outline based on analysis and prerequisites."""
    logging.info("Executing node: outline_structurer")
    try:
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
            "technical_concepts": str(state.analysis_result.technical_concepts) if state.analysis_result else "[]"
        }

        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["outline_structure"]["prompt"].format(**input_variables)
        response = await state.model.ainvoke(prompt)
        
        if not isinstance(response, str):
            # Extract JSON file 
            response = response.content
        
        logging.info(f"Outline Structure: {response}\n\n\n")
        
        # Parse and update state
        state.outline_structure = PROMPT_CONFIGS["outline_structure"]["parser"].parse(response)
        logging.info("Outline structure completed")
        
    except Exception as e:
        logging.error(f"Error in outline_structurer: {str(e)}")
        raise
    
    return state

async def final_generator(state: OutlineState) -> OutlineState:
    """Generates the final outline in markdown format."""
    logging.info("Executing node: final_generator")
    try:
        # Initialize persona service
        persona_service = PersonaService()
        persona_instructions = persona_service.get_persona_prompt("neuraforge")
        
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

        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["final_generation"]["prompt"].format(**input_variables)
        response = await state.model.ainvoke(prompt)
        
        if not isinstance(response, str):
            # Extract JSON file 
            response = response.content
        
        print(f"Final Generation Response: {response}\n\n\n")
        
        # Parse the response into FinalOutline format
        parsed_outline = PROMPT_CONFIGS["final_generation"]["parser"].parse(response)
        
        # Store the final outline
        state.final_outline = parsed_outline
        logging.info("Final outline generation completed")
        
    except Exception as e:
        logging.error(f"Error in final_generator: {str(e)}")
        raise
    
    return state
