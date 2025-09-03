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
    GENERATE_TITLES_PROMPT,
    SUGGEST_CLARITY_FLOW_IMPROVEMENTS_PROMPT, # Import the new prompt
    REDUCE_REDUNDANCY_PROMPT  # Import the redundancy reduction prompt
)

logger = logging.getLogger(__name__)

# --- Node Functions ---

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_introduction_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog introduction."""
    logger.info("Node: generate_introduction_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        prompt = GENERATE_INTRODUCTION_PROMPT.format(blog_draft=state.original_draft)
        response = await model.ainvoke(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Introduction generated successfully.")
            return {"introduction": response.strip()}
        else:
            logger.warning(f"Introduction generation returned empty/invalid response: {response}")
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
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        prompt = GENERATE_CONCLUSION_PROMPT.format(blog_draft=state.original_draft)
        response = await model.ainvoke(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Conclusion generated successfully.")
            return {"conclusion": response.strip()}
        else:
            logger.warning(f"Conclusion generation returned empty/invalid response: {response}")
            return {"error": "Failed to generate valid conclusion."}
    except Exception as e:
        logger.exception("Error in generate_conclusion_node")
        return {"error": f"Conclusion generation failed: {str(e)}"}

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_summary_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to generate the blog summary."""
    logger.info("Node: generate_summary_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        prompt = GENERATE_SUMMARY_PROMPT.format(blog_draft=state.original_draft)
        response = await model.ainvoke(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Summary generated successfully.")
            return {"summary": response.strip()}
        else:
            logger.warning(f"Summary generation returned empty/invalid response: {response}")
            return {"error": "Failed to generate valid summary."}
    except Exception as e:
        logger.exception("Error in generate_summary_node")
        return {"error": f"Summary generation failed: {str(e)}"}

# Corrected: Expect BlogRefinementState, use attribute access
async def generate_titles_node(state: BlogRefinementState, model: BaseModel, persona_service=None) -> Dict[str, Any]:
    """Node to generate title and subtitle options."""
    logger.info("Node: generate_titles_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        # Get persona instructions if persona_service is provided
        persona_instructions = ""
        if persona_service:
            persona_instructions = persona_service.get_persona_prompt("student_sharing")
        
        prompt = GENERATE_TITLES_PROMPT.format(
            persona_instructions=persona_instructions,
            blog_draft=state.original_draft
        )
        response = await model.ainvoke(prompt)

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
            # Nodes return dicts, so agent needs to handle parsing TitleOption list
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


async def suggest_clarity_flow_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to suggest clarity and flow improvements."""
    logger.info("Node: suggest_clarity_flow_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        # Use direct attribute access for refined_draft as well
        if not state.refined_draft:
            logger.error("Refined draft not found in state for clarity/flow suggestions.")
            return {"error": "Refined draft is missing, cannot generate clarity/flow suggestions."}

        prompt = SUGGEST_CLARITY_FLOW_IMPROVEMENTS_PROMPT.format(blog_draft=state.refined_draft)
        response = await model.ainvoke(prompt)
        if isinstance(response, str) and response.strip():
            logger.info("Clarity/flow suggestions generated successfully.")
            # Store the suggestions as a single string (bulleted list)
            return {"clarity_flow_suggestions": response.strip()}
        else:
            logger.warning(f"Clarity/flow suggestion generation returned empty/invalid response: {response}")
            # Decide if this is an error or just means no suggestions
            # For now, let's assume empty means no suggestions needed, not an error.
            return {"clarity_flow_suggestions": "No specific clarity or flow suggestions identified."}
    except Exception as e:
        logger.exception("Error in suggest_clarity_flow_node")
        return {"error": f"Clarity/flow suggestion generation failed: {str(e)}"}


async def reduce_redundancy_node(state: BlogRefinementState, model: BaseModel) -> Dict[str, Any]:
    """Node to reduce redundancy in the blog content."""
    logger.info("Node: reduce_redundancy_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        # Use the refined draft if available, otherwise use original draft
        draft_to_refine = state.refined_draft if state.refined_draft else state.original_draft
        
        if not draft_to_refine:
            logger.error("No draft found in state for redundancy reduction.")
            return {"error": "No draft available for redundancy reduction."}

        prompt = REDUCE_REDUNDANCY_PROMPT.format(blog_draft=draft_to_refine)
        response = await model.ainvoke(prompt)
        
        if isinstance(response, str) and response.strip():
            logger.info("Redundancy reduction completed successfully.")
            # Update the refined draft with the redundancy-reduced version
            return {"refined_draft": response.strip()}
        else:
            logger.warning(f"Redundancy reduction returned empty/invalid response: {response}")
            # If no reduction needed, keep the original
            return {"refined_draft": draft_to_refine}
    except Exception as e:
        logger.exception("Error in reduce_redundancy_node")
        return {"error": f"Redundancy reduction failed: {str(e)}"}


def assemble_refined_draft_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to assemble the final refined draft."""
    logger.info("Node: assemble_refined_draft_node")
    current_state = state.model_dump() if isinstance(state, BaseModel) else state
    if current_state.get('error'):
        logger.error(f"Skipping assembly due to previous error: {current_state.get('error')}")
        return {"error": current_state.get('error')}

    # Check if all required components are present in the state dictionary
    introduction = current_state.get('introduction')
    conclusion = current_state.get('conclusion')
    original_draft = current_state.get('original_draft')

    # Enhanced logging for prerequisite check
    logger.info(f"Assemble_refined_draft_node - Prerequisite check:")
    logger.info(f"  Introduction present: {bool(introduction)}")
    logger.info(f"  Conclusion present: {bool(conclusion)}")
    logger.info(f"  Original_draft present: {bool(original_draft)}")

    if not introduction or not conclusion or not original_draft:
        missing = []
        if not introduction: 
            missing.append("introduction")
            logger.warning("Assemble_refined_draft_node: Introduction is missing.")
        if not conclusion: 
            missing.append("conclusion")
            logger.warning("Assemble_refined_draft_node: Conclusion is missing.")
        if not original_draft: 
            missing.append("original_draft")
            logger.warning("Assemble_refined_draft_node: Original_draft is missing.")
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
