# -*- coding: utf-8 -*-
"""
Node functions for the Blog Refinement Agent's LangGraph.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import ValidationError, BaseModel

# Assuming BaseModel is correctly imported where needed or defined in state
from root.backend.agents.blog_refinement.state import BlogRefinementState, TitleOption
from root.backend.agents.blog_refinement.prompts import (
    GENERATE_INTRODUCTION_PROMPT,
    GENERATE_CONCLUSION_PROMPT,
    GENERATE_SUMMARY_PROMPT,
    GENERATE_TITLES_PROMPT
)

logger = logging.getLogger(__name__)

# --- Node Functions ---

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_introduction_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog introduction."""
    logger.info("Node: generate_introduction_node")
    if state.error: return {"error": state.error} # Use attribute access

    try:
        if not state.original_draft: # Check attribute
             return {"error": "Original draft missing in state for introduction generation."}
        prompt = GENERATE_INTRODUCTION_PROMPT.format(blog_draft=state.original_draft) # Use attribute access
        response_content = await model.ainvoke(prompt) # Correct model call: ainvoke
        if isinstance(response_content, str) and response_content.strip():
            cleaned_intro = response_content.strip()
            # Remove potential markdown fences
            if cleaned_intro.startswith("```markdown"):
                cleaned_intro = cleaned_intro[11:]
            elif cleaned_intro.startswith("```"):
                 cleaned_intro = cleaned_intro[3:]
            if cleaned_intro.endswith("```"):
                cleaned_intro = cleaned_intro[:-3]
            cleaned_intro = cleaned_intro.strip() # Strip again after removing fences
            logger.info("Introduction generated successfully.")
            return {"introduction": cleaned_intro}
        else:
            logger.warning(f"Introduction generation returned empty/invalid response: {response_content}")
            # Ensure error key is returned
            return {"error": "Failed to generate valid introduction."}
    except Exception as e:
        error_message = f"Introduction generation failed: {type(e).__name__} - {str(e)}"
        logger.exception("Error in generate_introduction_node")
        # Ensure error key is returned
        return {"error": error_message}

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_conclusion_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog conclusion."""
    logger.info("Node: generate_conclusion_node")
    if state.error: return {"error": state.error} # Use attribute access

    try:
        if not state.original_draft: # Check attribute
             return {"error": "Original draft missing in state for conclusion generation."}
        prompt = GENERATE_CONCLUSION_PROMPT.format(blog_draft=state.original_draft) # Use attribute access
        response_content = await model.ainvoke(prompt) # Correct model call: ainvoke
        if isinstance(response_content, str) and response_content.strip():
            cleaned_conclusion = response_content.strip()
            # Remove potential markdown fences
            if cleaned_conclusion.startswith("```markdown"):
                cleaned_conclusion = cleaned_conclusion[11:]
            elif cleaned_conclusion.startswith("```"):
                 cleaned_conclusion = cleaned_conclusion[3:]
            if cleaned_conclusion.endswith("```"):
                cleaned_conclusion = cleaned_conclusion[:-3]
            cleaned_conclusion = cleaned_conclusion.strip() # Strip again after removing fences
            logger.info("Conclusion generated successfully.")
            return {"conclusion": cleaned_conclusion}
        else:
            logger.warning(f"Conclusion generation returned empty/invalid response: {response_content}")
            return {"error": "Failed to generate valid conclusion."}
    except Exception as e:
        logger.exception("Error in generate_conclusion_node")
        return {"error": f"Conclusion generation failed: {str(e)}"}

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_summary_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog summary."""
    logger.info("Node: generate_summary_node")
    if state.error: return {"error": state.error} # Use attribute access

    try:
        if not state.original_draft: # Check attribute
             return {"error": "Original draft missing in state for summary generation."}
        prompt = GENERATE_SUMMARY_PROMPT.format(blog_draft=state.original_draft) # Use attribute access
        response_content = await model.ainvoke(prompt) # Correct model call: ainvoke
        if isinstance(response_content, str) and response_content.strip():
            cleaned_summary = response_content.strip()
            # Remove potential markdown fences
            if cleaned_summary.startswith("```markdown"):
                cleaned_summary = cleaned_summary[11:]
            elif cleaned_summary.startswith("```"):
                 cleaned_summary = cleaned_summary[3:]
            if cleaned_summary.endswith("```"):
                cleaned_summary = cleaned_summary[:-3]
            cleaned_summary = cleaned_summary.strip() # Strip again after removing fences
            logger.info("Summary generated successfully.")
            return {"summary": cleaned_summary}
        else:
            logger.warning(f"Summary generation returned empty/invalid response: {response_content}")
            return {"error": "Failed to generate valid summary."}
    except Exception as e:
        logger.exception("Error in generate_summary_node")
        return {"error": f"Summary generation failed: {str(e)}"}

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_titles_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate title and subtitle options."""
    logger.info("Node: generate_titles_node")
    if state.error: return {"error": state.error} # Use attribute access

    try:
        if not state.original_draft: # Check attribute
             return {"error": "Original draft missing in state for title generation."}
        prompt = GENERATE_TITLES_PROMPT.format(blog_draft=state.original_draft) # Use attribute access
        response_content = await model.ainvoke(prompt) # Correct model call: ainvoke
        logger.debug(f"Raw response from generate_titles: {response_content}") # Log raw response

        # Attempt to extract JSON block more robustly from response_content
        json_block = None
        try:
            # Find the start and end of the JSON list
            start_index = response_content.find('[')
            end_index = response_content.rfind(']')
            if start_index != -1 and end_index != -1 and end_index > start_index:
                json_string = response_content[start_index:end_index+1]
                # Basic validation if it looks like JSON
                if '{' in json_string and '}' in json_string:
                     json_block = json_string
                     logger.info("Extracted potential JSON block.")
            else:
                 logger.warning("Could not find JSON list markers '[]' in response.")
                 # Fallback: try cleaning ```json``` markers if list markers failed
                 cleaned_response = response_content.strip() # Use response_content
                 if cleaned_response.startswith("```json"):
                     cleaned_response = cleaned_response[7:]
                 if cleaned_response.endswith("```"):
                     cleaned_response = cleaned_response[:-3]
                 cleaned_response = cleaned_response.strip()
                 # Check if the cleaned response looks like a list
                 if cleaned_response.startswith('[') and cleaned_response.endswith(']'):
                      json_block = cleaned_response
                      logger.info("Extracted potential JSON block after cleaning ```json``` markers.")

        except Exception as extraction_err:
             logger.error(f"Error during JSON block extraction: {extraction_err}")
             json_block = None # Ensure json_block is None if extraction fails

        if not json_block:
             logger.error(f"Could not extract valid JSON block from LLM response for titles. Raw response: {response_content}")
             return {"error": "Failed to extract JSON title data from LLM response."}

        try:
            logger.debug(f"Attempting to parse JSON block: {json_block}")
            title_data = json.loads(json_block)
            if not isinstance(title_data, list):
                raise ValueError("Parsed JSON is not a list.")

            # Validate using Pydantic model (convert back to dict for storage in state)
            # Nodes return dicts, so agent needs to handle parsing TitleOption list
            options = [TitleOption.model_validate(item).model_dump() for item in title_data if isinstance(item, dict)]
            if not options:
                raise ValueError("No valid title options found after validation.")

            logger.info(f"Successfully generated {len(options)} title options.")
            return {"title_options": options} # Store list of dicts

        except (json.JSONDecodeError, ValueError, ValidationError) as parse_err: # Catch Pydantic validation errors too
            logger.error(f"Failed to parse/validate title options: {parse_err}. Raw response: {response_content}")
            return {"error": f"Failed to parse or validate title options: {parse_err}"}

    except Exception as e:
        logger.exception("Error in generate_titles_node")
        return {"error": f"Title generation failed: {str(e)}"}

# Corrected: Expect BlogRefinementState, use attribute access
def assemble_refined_draft_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to assemble the final refined draft."""
    logger.info("Node: assemble_refined_draft_node")
    if state.error:
        logger.error(f"Skipping assembly due to previous error: {state.error}") # Use attribute access
        return {"error": state.error}

    # Check if all required components are present using getattr for safety
    introduction = getattr(state, 'introduction', None)
    conclusion = getattr(state, 'conclusion', None)
    original_draft = getattr(state, 'original_draft', None) # Should always exist based on init

    if not introduction or not conclusion or not original_draft:
        missing = []
        # Check which specific attribute is None or empty after getattr
        if not introduction: missing.append('introduction')
        if not conclusion: missing.append('conclusion')
        if not original_draft: missing.append('original_draft (should not happen)')
        error_msg = f"Cannot assemble draft, missing components: {', '.join(missing)}."
        logger.error(error_msg)
        return {"error": error_msg}

    # Basic assembly logic (can be refined)
    # Assumes original_draft does not contain intro/conclusion sections to be replaced
    refined_content = (
        f"## Introduction\n\n{introduction}\n\n"
        f"{original_draft}\n\n"
        f"## Conclusion\n\n{conclusion}"
    )

    

    logger.info("Refined draft assembled successfully.")
    return {"refined_draft": refined_content}
