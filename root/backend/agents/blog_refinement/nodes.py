# -*- coding: utf-8 -*-
"""
Node functions for the Blog Refinement Agent's LangGraph.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import ValidationError, BaseModel

from backend.agents.cost_tracking_decorator import track_node_costs
from backend.agents.blog_refinement.state import BlogRefinementState, TitleOption
from backend.agents.blog_refinement.prompts import (
    GENERATE_INTRODUCTION_PROMPT,
    GENERATE_CONCLUSION_PROMPT,
    GENERATE_SUMMARY_PROMPT,
    GENERATE_TITLES_PROMPT,
    SUGGEST_CLARITY_FLOW_IMPROVEMENTS_PROMPT, # Import the new prompt
    REDUCE_REDUNDANCY_PROMPT  # Import the redundancy reduction prompt
)
from backend.agents.blog_refinement.prompt_builder import build_title_generation_prompt
from backend.agents.blog_refinement.validation import (
    validate_title_generation,
    create_correction_prompt
)
from backend.models.generation_config import TitleGenerationConfig
from backend.services.supabase_project_manager import MilestoneType

logger = logging.getLogger(__name__)

# --- Node Functions ---

# Corrected: Expect BlogRefinementState, use attribute access
@track_node_costs("generate_introduction", agent_name="BlogRefinementAgent", stage="refinement")
async def generate_introduction_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to generate the blog introduction."""
    logger.info("Node: generate_introduction_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        if not state.model:
            raise ValueError("Refinement state is missing model reference")

        prompt = GENERATE_INTRODUCTION_PROMPT.format(blog_draft=state.original_draft)
        response = await state.model.ainvoke(prompt)
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
@track_node_costs("generate_conclusion", agent_name="BlogRefinementAgent", stage="refinement")
async def generate_conclusion_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to generate the blog conclusion."""
    logger.info("Node: generate_conclusion_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        if not state.model:
            raise ValueError("Refinement state is missing model reference")

        prompt = GENERATE_CONCLUSION_PROMPT.format(blog_draft=state.original_draft)
        response = await state.model.ainvoke(prompt)
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
@track_node_costs("generate_summary", agent_name="BlogRefinementAgent", stage="refinement")
async def generate_summary_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to generate the blog summary."""
    logger.info("Node: generate_summary_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        if not state.model:
            raise ValueError("Refinement state is missing model reference")

        prompt = GENERATE_SUMMARY_PROMPT.format(blog_draft=state.original_draft)
        response = await state.model.ainvoke(prompt)
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
@track_node_costs("generate_titles", agent_name="BlogRefinementAgent", stage="refinement")
async def generate_titles_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to generate title and subtitle options with configuration support."""
    logger.info("Node: generate_titles_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        if not state.model:
            raise ValueError("Refinement state is missing model reference")

        # Use configuration if provided, otherwise use defaults
        config = state.title_config or TitleGenerationConfig()

        # Build dynamic prompt based on configuration
        prompt = build_title_generation_prompt(
            blog_draft=state.original_draft,
            config=config
        )

        logger.info(f"Generated prompt length: {len(prompt)}")
        logger.info(f"Title generation config: {config.num_titles} titles, "
                   f"{config.num_subtitles_per_title} subtitles each")

        # Initial generation attempt
        response = await state.model.ainvoke(prompt)

        # Clean and parse JSON
        cleaned_response = response.strip()
        
        # Enhanced debugging
        logger.info(f"Raw model response: '{response}'")
        logger.info(f"Response length: {len(response)}")
        logger.info(f"Response type: {type(response)}")
        
        # Handle empty response
        if not cleaned_response:
            logger.error("Model returned empty response")
            # Create fallback title options
            fallback_options = [{
                "title": "Technical Deep Dive",
                "subtitle": "Exploring key concepts and practical applications", 
                "reasoning": "Fallback title due to generation error"
            }]
            return {"title_options": fallback_options}
        
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()
        
        logger.info(f"Cleaned response: '{cleaned_response}'")

        try:
            title_data = json.loads(cleaned_response)
            if not isinstance(title_data, list):
                raise ValueError("Parsed JSON is not a list.")

            # Adapt parsing based on configuration
            validated_options = []
            for i, item in enumerate(title_data):
                if not isinstance(item, dict):
                    logger.warning(f"Item {i} is not a dictionary, skipping")
                    continue

                # Handle different subtitle structures based on config
                if config.num_subtitles_per_title == 1:
                    # Single subtitle structure
                    if "title" not in item or "subtitle" not in item:
                        logger.warning(f"Item {i} missing required fields, adding defaults")
                        item = {
                            "title": item.get("title", f"Blog Post Title {i+1}"),
                            "subtitle": item.get("subtitle", "Insights and practical applications"),
                            "reasoning": item.get("reasoning", item.get("approach", item.get("value_promise", "Generated title option")))
                        }

                    # Ensure reasoning field exists
                    if "reasoning" not in item:
                        item["reasoning"] = item.get("approach", item.get("value_promise", "Generated title option"))

                    try:
                        validated = TitleOption.model_validate(item).model_dump()
                        validated_options.append(validated)
                    except ValidationError as ve:
                        logger.warning(f"Validation error for item {i}: {ve}, using defaults")
                        validated_options.append({
                            "title": str(item.get("title", f"Blog Post Title {i+1}")),
                            "subtitle": str(item.get("subtitle", "Insights and practical applications")),
                            "reasoning": str(item.get("reasoning", "Generated title option"))
                        })
                else:
                    # Multiple subtitles structure
                    if "title" not in item:
                        # If we don't have a title field, check if this is a single-field structure
                        logger.warning(f"Item {i} missing 'title' field: {item}")
                        # Try to provide a fallback
                        validated_item = {
                            "title": str(item) if isinstance(item, str) else f"Blog Post Title {i+1}",
                            "subtitle": "Insights and practical applications",
                            "reasoning": "Generated title option with defaults"
                        }
                    elif "subtitles" in item and item["subtitles"]:
                        # Handle multiple subtitles structure
                        first_subtitle = item["subtitles"][0] if isinstance(item["subtitles"], list) else item["subtitles"]
                        if isinstance(first_subtitle, dict):
                            subtitle_text = first_subtitle.get("subtitle", "Insights and practical applications")
                        else:
                            subtitle_text = str(first_subtitle)

                        validated_item = {
                            "title": item["title"],
                            "subtitle": subtitle_text,
                            "reasoning": item.get("reasoning", "Generated title option")
                        }
                    elif "subtitle" in item:
                        # Single subtitle in multi-subtitle mode (fallback)
                        validated_item = {
                            "title": item["title"],
                            "subtitle": item["subtitle"],
                            "reasoning": item.get("reasoning", "Generated title option")
                        }
                    else:
                        # No subtitle field at all - provide default
                        logger.warning(f"Item {i} has title but no subtitle: {item}")
                        validated_item = {
                            "title": item["title"],
                            "subtitle": "Exploring key concepts and practical insights",
                            "reasoning": item.get("reasoning", "Generated title option")
                        }

                    try:
                        validated = TitleOption.model_validate(validated_item).model_dump()
                        validated_options.append(validated)
                    except ValidationError as ve:
                        logger.warning(f"Validation error for item {i}: {ve}, using fallback")
                        # Provide a safe fallback
                        validated_options.append({
                            "title": str(item.get("title", f"Blog Post Title {i+1}")),
                            "subtitle": "Insights and practical applications",
                            "reasoning": "Generated title option with defaults due to validation error"
                        })

            if not validated_options:
                raise ValueError("No valid title options found after validation.")

            # Validate against configuration requirements
            validation_result = validate_title_generation(validated_options, config)

            if not validation_result.is_valid:
                logger.warning(f"Title generation validation failed: {validation_result.violations}")

                # Single retry with correction prompt
                correction_prompt = create_correction_prompt(
                    validated_options,
                    validation_result,
                    content_type="titles"
                )

                logger.info("Attempting to correct title generation with feedback")
                retry_response = await state.model.ainvoke(correction_prompt)

                # Parse retry response
                cleaned_retry = retry_response.strip()
                if cleaned_retry.startswith("```json"):
                    cleaned_retry = cleaned_retry[7:]
                if cleaned_retry.endswith("```"):
                    cleaned_retry = cleaned_retry[:-3]
                cleaned_retry = cleaned_retry.strip()

                try:
                    retry_data = json.loads(cleaned_retry)
                    # Process retry data (similar to above)
                    # For brevity, we'll use the retry data as-is if valid
                    if isinstance(retry_data, list) and len(retry_data) == config.num_titles:
                        validated_options = retry_data
                        logger.info("Title generation corrected successfully")
                    else:
                        logger.warning("Retry still doesn't meet requirements, using original")
                except json.JSONDecodeError:
                    logger.error("Failed to parse retry response, using original")

            if validation_result.warnings:
                logger.info(f"Title generation warnings: {validation_result.warnings}")

            logger.info(f"Successfully generated {len(validated_options)} title options.")
            return {"title_options": validated_options}

        except (json.JSONDecodeError, ValueError) as parse_err:
            logger.error(f"Failed to parse title options: {parse_err}. Raw response: '{response}', Cleaned: '{cleaned_response}'")
            # Create fallback title options on parse error
            fallback_options = [
                {
                    "title": "Technical Deep Dive", 
                    "subtitle": "Exploring concepts and implementation details",
                    "reasoning": "Default title due to generation error"
                },
                {
                    "title": "Practical Guide",
                    "subtitle": "Step-by-step approach and best practices",
                    "reasoning": "Alternative title option"
                },
                {
                    "title": "Technical Analysis",
                    "subtitle": "Key insights and practical considerations",
                    "reasoning": "Third fallback option"
                }
            ]
            return {"title_options": fallback_options}

    except Exception as e:
        logger.exception("Error in generate_titles_node")
        return {"error": f"Title generation failed: {str(e)}"}


@track_node_costs("suggest_clarity_flow", agent_name="BlogRefinementAgent", stage="refinement")
async def suggest_clarity_flow_node(state: BlogRefinementState) -> Dict[str, Any]:
    """Node to suggest clarity and flow improvements."""
    logger.info("Node: suggest_clarity_flow_node")
    # Access Pydantic model fields directly
    if state.error: return {"error": state.error}

    try:
        # Use direct attribute access for refined_draft as well
        if not state.refined_draft:
            logger.error("Refined draft not found in state for clarity/flow suggestions.")
            return {"error": "Refined draft is missing, cannot generate clarity/flow suggestions."}

        if not state.model:
            raise ValueError("Refinement state is missing model reference")

        # Track input word count
        input_words = len(state.refined_draft.split())
        logger.info(f"Input word count: {input_words}")

        prompt = SUGGEST_CLARITY_FLOW_IMPROVEMENTS_PROMPT.format(blog_draft=state.refined_draft)
        response = await state.model.ainvoke(prompt)

        if isinstance(response, str) and response.strip():
            # Track output word count
            output_words = len(response.strip().split())
            word_change = output_words - input_words
            percent_change = (output_words / max(input_words, 1) * 100 - 100)

            logger.info(f"Output word count: {output_words}")
            logger.info(f"Word count change: {word_change:+d} ({percent_change:+.1f}%)")

            # Warning if significant reduction
            if output_words < input_words * 0.9:  # >10% reduction
                logger.warning(f"Significant content reduction detected: {input_words} → {output_words} words ({percent_change:.1f}%)")

            clarity_suggestions = response.strip()

            # NEW: Save BLOG_REFINED milestone to SQL if sql_project_manager is available
            if hasattr(state, 'sql_project_manager') and state.sql_project_manager and hasattr(state, 'project_id') and state.project_id:
                try:
                    milestone_data = {
                        "refined_draft": state.refined_draft or "",
                        "summary": state.summary or "",
                        "title_options": [
                            {
                                "title": opt.title if hasattr(opt, 'title') else opt.get('title', ''),
                                "subtitle": opt.subtitle if hasattr(opt, 'subtitle') else opt.get('subtitle', ''),
                                "reasoning": opt.reasoning if hasattr(opt, 'reasoning') else opt.get('reasoning', '')
                            } for opt in (state.title_options or [])
                        ],
                        "clarity_flow_suggestions": clarity_suggestions,
                        "iteration_count": getattr(state, 'iteration_count', 0)
                    }
                    await state.sql_project_manager.save_milestone(
                        project_id=state.project_id,
                        milestone_type=MilestoneType.BLOG_REFINED,
                        data=milestone_data
                    )
                    logger.info(f"Saved BLOG_REFINED milestone for project {state.project_id}")
                except Exception as e:
                    logger.error(f"Failed to save refinement milestone: {e}")
                    # Don't fail the workflow for SQL errors

            # Store the suggestions as a single string (bulleted list)
            return {"clarity_flow_suggestions": clarity_suggestions}
        else:
            logger.warning(f"Clarity/flow suggestion generation returned empty/invalid response: {response}")
            # Decide if this is an error or just means no suggestions
            # For now, let's assume empty means no suggestions needed, not an error.
            return {"clarity_flow_suggestions": "No specific clarity or flow suggestions identified."}
    except Exception as e:
        logger.exception("Error in suggest_clarity_flow_node")
        return {"error": f"Clarity/flow suggestion generation failed: {str(e)}"}


@track_node_costs("reduce_redundancy", agent_name="BlogRefinementAgent", stage="refinement")
async def reduce_redundancy_node(state: BlogRefinementState) -> Dict[str, Any]:
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

        if not state.model:
            raise ValueError("Refinement state is missing model reference")

        prompt = REDUCE_REDUNDANCY_PROMPT.format(blog_draft=draft_to_refine)
        response = await state.model.ainvoke(prompt)
        
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


def validate_content_preservation(original: str, refined: str) -> Dict[str, Any]:
    """Validate that refinement didn't lose critical content."""
    orig_words = len(original.split())
    refined_words = len(refined.split())

    # Check for major sections that should be present
    missing_sections = []

    # Check if code blocks are preserved
    orig_code_blocks = original.count("```")
    refined_code_blocks = refined.count("```")
    if orig_code_blocks > refined_code_blocks:
        missing_sections.append("code blocks")

    # Check for LaTeX formulas
    orig_formulas = original.count("$$")
    refined_formulas = refined.count("$$")
    if orig_formulas > refined_formulas:
        missing_sections.append("mathematical formulas")

    # Word count check
    word_ratio = refined_words / max(orig_words, 1)
    if word_ratio < 0.85:  # More than 15% reduction
        logger.warning(f"Content reduction too aggressive: {orig_words}→{refined_words} words ({word_ratio:.1%})")

    return {
        "word_count_ratio": word_ratio,
        "missing_sections": missing_sections,
        "preservation_ok": word_ratio >= 0.85 and not missing_sections
    }
