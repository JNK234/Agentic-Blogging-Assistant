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

async def generate_introduction_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog introduction."""
    logger.info("Node: generate_introduction_node")
    # LangGraph passes state as a dict, access keys directly
    current_state = state
    if current_state.get('error'): return {"error": current_state['error']}

    try:
        prompt = GENERATE_INTRODUCTION_PROMPT.format(blog_draft=current_state['original_draft'])
        response = await model.generate(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Introduction generated successfully.")
            return {"introduction": response.strip()}
        else:
            logger.warning(f"Introduction generation returned empty/invalid response: {response}")
            return {"error": "Failed to generate valid introduction."}
    except Exception as e:
        logger.exception("Error in generate_introduction_node")
        return {"error": f"Introduction generation failed: {str(e)}"}

async def generate_conclusion_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog conclusion."""
    logger.info("Node: generate_conclusion_node")
    current_state = state
    if current_state.get('error'): return {"error": current_state['error']}

    try:
        prompt = GENERATE_CONCLUSION_PROMPT.format(blog_draft=current_state['original_draft'])
        response = await model.generate(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Conclusion generated successfully.")
            return {"conclusion": response.strip()}
        else:
            logger.warning(f"Conclusion generation returned empty/invalid response: {response}")
            return {"error": "Failed to generate valid conclusion."}
    except Exception as e:
        logger.exception("Error in generate_conclusion_node")
        return {"error": f"Conclusion generation failed: {str(e)}"}

async def generate_summary_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog summary."""
    logger.info("Node: generate_summary_node")
    current_state = state
    if current_state.get('error'): return {"error": current_state['error']}

    try:
        prompt = GENERATE_SUMMARY_PROMPT.format(blog_draft=current_state['original_draft'])
        response = await model.generate(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Summary generated successfully.")
            return {"summary": response.strip()}
        else:
            logger.warning(f"Summary generation returned empty/invalid response: {response}")
            return {"error": "Failed to generate valid summary."}
    except Exception as e:
        logger.exception("Error in generate_summary_node")
        return {"error": f"Summary generation failed: {str(e)}"}

async def generate_titles_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate title and subtitle options."""
    logger.info("Node: generate_titles_node")
    current_state = state
    if current_state.get('error'): return {"error": current_state['error']}

    try:
        prompt = GENERATE_TITLES_PROMPT.format(blog_draft=current_state['original_draft'])
        response = await model.generate(prompt)

        # Clean and parse JSON
        cleaned_response = response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()

        try:
            title_data = json.loads(cleaned_response)
            if not isinstance(title_data, list):
                raise ValueError("Parsed JSON is not a list.")

            # Validate using Pydantic model (convert back to dict for storage in state)
            options = [TitleOption.model_validate(item).model_dump() for item in title_data if isinstance(item, dict)]
            if not options:
                raise ValueError("No valid title options found after validation.")

            logger.info(f"Successfully generated {len(options)} title options.")
            return {"title_options": options} # Store list of dicts

        except (json.JSONDecodeError, ValueError, ValidationError) as parse_err: # Catch Pydantic validation errors too
            logger.error(f"Failed to parse/validate title options: {parse_err}. Raw response: {response}")
            return {"error": f"Failed to parse or validate title options: {parse_err}"}

    except Exception as e:
        logger.exception("Error in generate_titles_node")
        return {"error": f"Title generation failed: {str(e)}"}

def assemble_refined_draft_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to assemble the final refined draft."""
    logger.info("Node: assemble_refined_draft_node")
    current_state = state
    if current_state.get('error'):
        logger.error(f"Skipping assembly due to previous error: {current_state['error']}")
        # Ensure the error is propagated if not already set explicitly in the state dict key
        return {"error": current_state['error']}

    # Check if all required components are present in the state dictionary
    introduction = current_state.get('introduction')
    conclusion = current_state.get('conclusion')
    original_draft = current_state.get('original_draft')

    if not introduction or not conclusion or not original_draft:
        missing = [k for k, v in {'introduction': introduction, 'conclusion': conclusion, 'original_draft': original_draft}.items() if not v]
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
