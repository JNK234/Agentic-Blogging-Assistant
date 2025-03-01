import logging
from typing import Dict, List, Any
from root.backend.utils.file_parser import ParsedContent
from root.backend.agents.outline_generator.state import OutlineState
from root.backend.agents.outline_generator.prompts import PROMPT_CONFIGS

logging.basicConfig(level=logging.INFO)

async def analyze_content(state: OutlineState) -> OutlineState:
    """Analyzes the content using LLM to extract key information."""
    logging.info("Executing node: analyze_content")
    try:
        # Prepare input variables for the prompt
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["content_analysis"]["parser"].get_format_instructions(),
            "notebook_content_main_content": state.notebook_content.main_content,
            "notebook_content_code_segments": str(state.notebook_content.code_segments),
            "markdown_content_main_content": state.markdown_content.main_content,
            "markdown_content_code_segments": str(state.markdown_content.code_segments),
            "notebook_content_metadata": str(state.notebook_content.metadata),
            "markdown_content_metadata": str(state.markdown_content.metadata)
        }

        # Get the prompt and format it
        prompt = PROMPT_CONFIGS["content_analysis"]["prompt"].format(**input_variables)
        
        # print(f"Input Prompt: {prompt}")
        
        # Get LLM response
        response = await state.model.ainvoke(prompt)
        
        print(f"Content Analysis Response: {response.content}\n\n\n")
        
        # Parse the response
        state.analysis_result = PROMPT_CONFIGS["content_analysis"]["parser"].parse(response.content)
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
        
        print(f"Difficulty Assessment Response: {response.content}\n\n\n")
        
        # Parse and update state
        state.difficulty_level = PROMPT_CONFIGS["difficulty_assessment"]["parser"].parse(response.content)
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
        
        logging.info(f"Prerquisite Identifier: {response.content}\n\n\n")
        
        # Parse and update state
        state.prerequisites = PROMPT_CONFIGS["prerequisites"]["parser"].parse(response.content)
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
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["outline_structure"]["parser"].get_format_instructions(),
            "main_topics": str(state.analysis_result.main_topics),
            "difficulty_level": state.difficulty_level.level if state.difficulty_level else "",
            "prerequisites": {
                "required_knowledge": state.prerequisites.required_knowledge,
                "recommended_tools": state.prerequisites.recommended_tools,
                "setup_instructions": state.prerequisites.setup_instructions
            } if state.prerequisites else {}
        }

        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["outline_structure"]["prompt"].format(**input_variables)
        response = await state.model.ainvoke(prompt)
        
        logging.info(f"Outline Structutre: {response.content}\n\n\n")
        
        # Parse and update state
        state.outline_structure = PROMPT_CONFIGS["outline_structure"]["parser"].parse(response.content)
        logging.info("Outline structure completed")
        
    except Exception as e:
        logging.error(f"Error in outline_structurer: {str(e)}")
        raise
    
    return state

async def final_generator(state: OutlineState) -> OutlineState:
    """Generates the final outline in markdown format."""
    logging.info("Executing node: final_generator")
    try:
        # Prepare input variables
        input_variables = {
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
        
        print(f"Final Generation Response: {response.content}\n\n\n")
        
        # Parse the response into FinalOutline format
        parsed_outline = PROMPT_CONFIGS["final_generation"]["parser"].parse(response.content)
        
        # Store the final outline
        state.final_outline = parsed_outline
        logging.info("Final outline generation completed")
        
    except Exception as e:
        logging.error(f"Error in final_generator: {str(e)}")
        raise
    
    return state
