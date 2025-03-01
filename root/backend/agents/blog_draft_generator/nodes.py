import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import re
from root.backend.agents.blog_draft_generator.state import BlogDraftState, DraftSection, ContentReference, CodeExample, SectionVersion, SectionFeedback
from root.backend.agents.blog_draft_generator.prompts import PROMPT_CONFIGS
from root.backend.agents.blog_draft_generator.utils import (
    extract_code_blocks,
    format_content_references,
    extract_section_metrics,
    parse_json_safely,
    format_code_examples,
    generate_table_of_contents
)
from root.backend.services.vector_store_service import VectorStoreService

logging.basicConfig(level=logging.INFO)

async def semantic_content_mapper(state: BlogDraftState) -> BlogDraftState:
    """Maps content to sections using vector search for semantic matching."""
    logging.info("Executing node: semantic_content_mapper")
    
    # Initialize vector store service if not already available
    vector_store = VectorStoreService()
    content_mapping = {}
    
    # Set generation stage
    state.generation_stage = "mapping"
    
    # For each section in the outline, use vector search to find relevant content
    for section in state.outline.sections:
        section_title = section.title
        learning_goals = section.learning_goals
        
        # Create a rich query combining section title and learning goals
        query = f"{section_title}: {', '.join(learning_goals)}"
        logging.info(f"Searching for content relevant to: {query}")
        
        # Search for markdown content first (with higher result count)
        markdown_results = vector_store.search_content(
            query=query,
            metadata_filter={"source_type": "markdown"},
            n_results=15  # Get more markdown results
        )
        
        # Search for code examples
        code_results = vector_store.search_content(
            query=query,
            metadata_filter={"source_type": "code"},
            n_results=10
        )
        
        # Convert search results to ContentReference objects
        references = []
        
        # Process markdown results (prioritized)
        for result in markdown_results:
            reference = ContentReference(
                content=result["content"],
                source_type="markdown",
                relevance_score=min(1.0, result["relevance"] + 0.1),  # Boost markdown relevance
                category=result["metadata"].get("category", "concept"),
                source_location=result["metadata"].get("source_location", "")
            )
            references.append(reference)
        
        # Process code results
        for result in code_results:
            # Only include code with sufficient relevance
            if result["relevance"] > 0.6:
                reference = ContentReference(
                    content=result["content"],
                    source_type="code",
                    relevance_score=result["relevance"],
                    category="code_example",
                    source_location=result["metadata"].get("source_location", "")
                )
                references.append(reference)
                
                # Try to find context for this code
                code_context = vector_store.search_content(
                    query=result["content"][:100],  # Use start of code as query
                    metadata_filter={"source_type": "markdown"},
                    n_results=2
                )
                
                # Add context as separate reference if found
                if code_context:
                    context_reference = ContentReference(
                        content=code_context[0]["content"],
                        source_type="code_context",
                        relevance_score=result["relevance"] - 0.1,  # Slightly lower relevance
                        category="code_explanation",
                        source_location=code_context[0]["metadata"].get("source_location", "")
                    )
                    references.append(context_reference)
        
        # Sort references by relevance
        references.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Use LLM to validate and enhance the most relevant content
        if references:
            # Take top 10 references for LLM validation
            top_references = references[:10]
            formatted_references = "\n\n".join([
                f"Content: {ref.content[:300]}...\n"
                f"Type: {ref.source_type}\n"
                f"Relevance: {ref.relevance_score}\n"
                f"Category: {ref.category}"
                for ref in top_references
            ])
            
            # Prepare input variables for the prompt
            input_variables = {
                "format_instructions": PROMPT_CONFIGS["content_validation"]["parser"].get_format_instructions(),
                "section_title": section_title,
                "learning_goals": ", ".join(learning_goals),
                "content_references": formatted_references
            }
            
            # Format prompt and get LLM response
            prompt = PROMPT_CONFIGS["content_validation"]["prompt"].format(**input_variables)
            
            try:
                response = await state.model.ainvoke(prompt)
                logging.info(f"\n\nContent validation response for section {section_title}:\n{response.content}\n\n")
                
                # Parse the response to get validated references
                validated_items = parse_json_safely(response.content, [])
                
                # Update references with LLM validation
                if validated_items:
                    # Create new references list with validated items
                    validated_references = []
                    for item in validated_items:
                        # Find the original reference
                        for ref in top_references:
                            if item.get("content_snippet") in ref.content:
                                # Create updated reference with LLM validation
                                validated_ref = ContentReference(
                                    content=ref.content,
                                    source_type=ref.source_type,
                                    relevance_score=item.get("adjusted_relevance", ref.relevance_score),
                                    category=item.get("category", ref.category),
                                    source_location=ref.source_location
                                )
                                validated_references.append(validated_ref)
                                break
                    
                    # Add any remaining references that weren't in the top 10
                    if len(validated_references) > 0:
                        content_mapping[section_title] = validated_references + references[10:]
                    else:
                        content_mapping[section_title] = references
                else:
                    content_mapping[section_title] = references
            except Exception as e:
                logging.error(f"Error validating content for section {section_title}: {e}")
                content_mapping[section_title] = references
        else:
            content_mapping[section_title] = []
    
    state.content_mapping = content_mapping
    return state

async def section_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates content for current section."""
    logging.info("Executing node: section_generator")
    print(f"Section generator - Starting generation for section index {state.current_section_index}")
    
    # Update generation stage
    state.generation_stage = "drafting"
    
    if state.current_section_index >= len(state.outline.sections):
        logging.info("All sections have been generated.")
        print("All sections have been generated.")
        return state
    
    section = state.outline.sections[state.current_section_index]
    section_title = section.title
    learning_goals = section.learning_goals
    
    print(f"Section generator - Generating content for '{section_title}'")
    
    # Get relevant content for this section
    relevant_content = state.content_mapping.get(section_title, [])
    
    # Format content for the prompt using utility function
    formatted_content = format_content_references(relevant_content)
    
    # Get previous section content for context if available
    previous_context = ""
    if state.current_section_index > 0 and state.sections:
        prev_section = state.sections[-1]
        previous_context = f"""
        Previous Section: {prev_section.title}
        Content Summary: {prev_section.content}...
        """
    
    # Prepare input variables for the prompt
    input_variables = {
        "format_instructions": PROMPT_CONFIGS["section_generation"]["parser"].get_format_instructions() if PROMPT_CONFIGS["section_generation"]["parser"] else "",
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "formatted_content": formatted_content,
        "previous_context": previous_context
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["section_generation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        # Log the response content
        logging.info(f"\n\nSection generation response for {section_title}:\n{response.content}\n\n")
        
        # Create a new draft section
        draft_section = DraftSection(
            title=section_title,
            content=response.content,
            feedback=[],
            versions=[],
            current_version=1,
            status="draft"
        )
        
        # Extract key concepts and technical terms
        # This could be enhanced with NLP in a future version
        draft_section.key_concepts = learning_goals
        
        # Add to sections list
        state.sections.append(draft_section)
        state.current_section = draft_section
        state.current_section_index += 1
        
    except Exception as e:
        logging.error(f"Error generating section: {e}")
        state.errors.append(f"Section generation failed: {str(e)}")
        return state
    
    return state

async def content_enhancer(state: BlogDraftState) -> BlogDraftState:
    """Enhances section content."""
    logging.info("Executing node: content_enhancer")
    
    # Update generation stage
    state.generation_stage = "enhancing"
    
    if state.current_section is None:
        logging.warning("No current section to enhance.")
        return state
    
    section_title = state.current_section.title
    section_index = state.current_section_index - 1  # Adjust for 0-based indexing
    learning_goals = state.outline.sections[section_index].learning_goals
    relevant_content = state.content_mapping.get(section_title, [])
    existing_content = state.current_section.content
    
    # Format content for the prompt using utility function
    # Only use high-relevance content for enhancement
    high_relevance_content = [ref for ref in relevant_content if ref.relevance_score > 0.5]
    formatted_content = format_content_references(high_relevance_content)
    
    # Prepare input variables for the prompt
    input_variables = {
        "format_instructions": PROMPT_CONFIGS["content_enhancement"]["parser"].get_format_instructions() if PROMPT_CONFIGS["content_enhancement"]["parser"] else "",
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "existing_content": existing_content,
        "formatted_content": formatted_content
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["content_enhancement"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        # Log the response content
        logging.info(f"\n\nContent enhancement response for {section_title}:\n{response.content}\n\n")
        
        # Store the original content as a version
        state.current_section.versions.append(SectionVersion(
            content=state.current_section.content,
            version_number=state.current_section.current_version,
            timestamp=datetime.now().isoformat(),
            changes="Initial enhancement"
        ))
        
        # Update the section content
        state.current_section.content = response.content
        state.current_section.current_version += 1
        
    except Exception as e:
        logging.error(f"Error enhancing section: {e}")
        state.errors.append(f"Section enhancement failed: {str(e)}")
        return state
    
    return state

async def code_example_extractor(state: BlogDraftState) -> BlogDraftState:
    """Extracts and improves code examples from the section content."""
    logging.info("Executing node: code_example_extractor")
    
    if state.current_section is None:
        logging.warning("No current section to extract code from.")
        return state
    
    section_content = state.current_section.content
    
    # Extract code blocks using utility function
    code_blocks = extract_code_blocks(section_content)
    
    if not code_blocks:
        logging.info("No code blocks found in section.")
        return state
    
    code_examples = []
    
    for i, block in enumerate(code_blocks):
        language = block["language"]
        code = block["code"]
        
        # Extract context around the code block
        code_pos = section_content.find(f"```{language}\n{code}```")
        start_pos = max(0, code_pos - 200)
        end_pos = min(len(section_content), code_pos + len(f"```{language}\n{code}```") + 200)
        context = section_content[start_pos:end_pos]
        
        # Prepare input variables for the prompt
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["code_example_extraction"]["parser"].get_format_instructions() if PROMPT_CONFIGS["code_example_extraction"]["parser"] else "",
            "language": language,
            "code": code,
            "context": context
        }
        
        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["code_example_extraction"]["prompt"].format(**input_variables)
        
        try:
            response = await state.model.ainvoke(prompt)
            
            # Log the response content
            logging.info(f"\n\nCode example extraction response for example {i+1}:\n{response.content}\n\n")
            
            # Parse the response
            result = parse_json_safely(response.content, {})
            
            code_example = CodeExample(
                code=result.get("code", code),
                language=result.get("language", language),
                description=result.get("description", f"Code example {i+1}"),
                explanation=result.get("explanation", ""),
                output=result.get("output"),
                source_location=result.get("source_location", f"Section: {state.current_section.title}")
            )
            
            code_examples.append(code_example)
                
        except Exception as e:
            logging.error(f"Error analyzing code example: {e}")
            # Add the original code as a fallback
            code_example = CodeExample(
                code=code,
                language=language,
                description=f"Code example {i+1}",
                explanation="",
                source_location=f"Section: {state.current_section.title}"
            )
            code_examples.append(code_example)
    
    # Store the extracted code examples
    state.current_section.code_examples = code_examples
    
    return state

async def quality_validator(state: BlogDraftState) -> BlogDraftState:
    """Validates the quality of the current section."""
    logging.info("Executing node: quality_validator")
    print(f"Quality validator - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    # Update generation stage
    state.generation_stage = "validating"
    
    if state.current_section is None:
        logging.warning("No current section to validate.")
        return state
    
    section_title = state.current_section.title
    section_index = state.current_section_index - 1
    learning_goals = state.outline.sections[section_index].learning_goals
    section_content = state.current_section.content
    
    # Prepare input variables for the prompt
    input_variables = {
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "section_content": section_content
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["quality_validation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        # Log the response content
        logging.info(f"\n\nQuality validation response for {section_title}:\n{response.content}\n\n")
        
        # Parse the response
        result = parse_json_safely(response.content, {})
        
        # Store quality metrics
        state.current_section.quality_metrics = {
            "completeness": result.get("completeness", 0.0),
            "technical_accuracy": result.get("technical_accuracy", 0.0),
            "clarity": result.get("clarity", 0.0),
            "code_quality": result.get("code_quality", 0.0),
            "engagement": result.get("engagement", 0.0),
            "overall_score": result.get("overall_score", 0.0)
        }
        
        # Calculate overall score if not provided
        if "overall_score" not in state.current_section.quality_metrics:
            metrics = state.current_section.quality_metrics
            overall = sum([
                metrics.get("completeness", 0.0),
                metrics.get("technical_accuracy", 0.0),
                metrics.get("clarity", 0.0),
                metrics.get("code_quality", 0.0),
                metrics.get("engagement", 0.0)
            ]) / 5.0
            state.current_section.quality_metrics["overall_score"] = overall
            print(f"Calculated overall score: {overall}")
        
        # Determine if improvement is needed based on overall score
        overall_score = state.current_section.quality_metrics.get("overall_score", 0.0)
        improvement_needed = overall_score < 0.85  # Set a threshold for quality
        print(f"Overall score: {overall_score}, Improvement needed: {improvement_needed}")
        
        # Increment iteration count
        state.iteration_count += 1
        print(f"Incremented iteration count to: {state.iteration_count}")
        
        # If improvement is needed and we haven't reached max iterations, continue
        if improvement_needed and state.iteration_count < state.max_iterations:
            print(f"Improvement needed and iteration count ({state.iteration_count}) < max iterations ({state.max_iterations})")
            state.status["current_section"] = f"Needs improvement (iteration {state.iteration_count})"
        else:
            # Section is good enough or we've reached max iterations
            print(f"Section is good enough or max iterations reached. Iteration count: {state.iteration_count}")
            state.status["current_section"] = "Ready for finalization"
            state.completed_sections.add(section_index)
            
    except Exception as e:
        logging.error(f"Error validating section quality: {e}")
        state.errors.append(f"Quality validation failed: {str(e)}")
        state.iteration_count += 1
        print(f"Error in quality validator. Incremented iteration count to: {state.iteration_count}")
    
    return state

async def auto_feedback_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates automatic feedback for the current section."""
    logging.info("Executing node: auto_feedback_generator")
    print(f"Auto feedback generator - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    if state.current_section is None:
        logging.warning("No current section to generate feedback for.")
        print("No current section to generate feedback for.")
        return state
    
    # Get quality metrics if available
    quality_metrics = getattr(state.current_section, "quality_metrics", {})
    print(f"Quality metrics: {quality_metrics}")
    
    # Generate specific feedback based on quality metrics
    feedback_points = []
    
    if quality_metrics.get("completeness", 1.0) < 0.8:
        feedback_points.append("Ensure all learning goals are thoroughly covered.")
    
    if quality_metrics.get("technical_accuracy", 1.0) < 0.8:
        feedback_points.append("Verify technical accuracy and provide more precise explanations.")
    
    if quality_metrics.get("clarity", 1.0) < 0.8:
        feedback_points.append("Improve clarity by breaking down complex concepts.")
    
    if quality_metrics.get("code_quality", 1.0) < 0.8:
        feedback_points.append("Enhance code examples with better comments and explanations.")
    
    if quality_metrics.get("engagement", 1.0) < 0.8:
        feedback_points.append("Make the content more engaging with real-world applications.")
    
    # If no specific issues, provide general enhancement feedback
    if not feedback_points:
        feedback_points = ["Add more technical depth and practical examples."]
    
    # Set the feedback
    feedback = "Automatic feedback:\n- " + "\n- ".join(feedback_points)
    print(f"Generated feedback: {feedback}")
    
    # Add feedback to the section
    state.current_section.feedback.append(SectionFeedback(
        content=feedback,
        source="auto",
        timestamp=datetime.now().isoformat(),
        addressed=False
    ))
    print(f"Added feedback to section '{state.current_section.title}'")
    
    return state

async def feedback_incorporator(state: BlogDraftState) -> BlogDraftState:
    """Incorporates feedback into the section content."""
    logging.info("Executing node: feedback_incorporator")
    print(f"Feedback incorporator - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    if state.current_section is None:
        logging.warning("No current section to incorporate feedback.")
        print("No current section to incorporate feedback.")
        return state
    
    # Get the most recent feedback that hasn't been addressed
    unaddressed_feedback = [f for f in state.current_section.feedback if not f.addressed]
    if not unaddressed_feedback:
        logging.info("No unaddressed feedback to incorporate.")
        print("No unaddressed feedback to incorporate.")
        return state
    
    feedback = unaddressed_feedback[-1].content
    print(f"Found unaddressed feedback: {feedback[:50]}...")
    
    section_title = state.current_section.title
    section_index = state.current_section_index - 1
    learning_goals = state.outline.sections[section_index].learning_goals
    existing_content = state.current_section.content
    
    # Prepare input variables for the prompt
    input_variables = {
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "existing_content": existing_content,
        "feedback": feedback
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["feedback_incorporation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        # Log the response content
        logging.info(f"\n\nFeedback incorporation response for {section_title}:\n{response.content}\n\n")
        
        # Store the original content as a version
        state.current_section.versions.append(SectionVersion(
            content=state.current_section.content,
            version_number=state.current_section.current_version,
            timestamp=datetime.now().isoformat(),
            changes=f"Feedback incorporation: {feedback[:50]}..."
        ))
        
        # Update the section content and version
        state.current_section.content = response.content
        state.current_section.current_version += 1
        
        # Mark feedback as addressed
        for f in unaddressed_feedback:
            f.addressed = True
        
    except Exception as e:
        logging.error(f"Error incorporating feedback: {e}")
        state.errors.append(f"Feedback incorporation failed: {str(e)}")
    
    return state

async def section_finalizer(state: BlogDraftState) -> BlogDraftState:
    """Finalizes the current section."""
    logging.info("Executing node: section_finalizer")
    print(f"Section finalizer - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    # Update generation stage
    state.generation_stage = "finalizing"
    
    if state.current_section is None:
        logging.warning("No current section to finalize.")
        print("No current section to finalize.")
        return state
    
    # Log the section content to ensure it's captured
    section_title = state.current_section.title
    section_content_preview = state.current_section.content[:200] + "..." if len(state.current_section.content) > 200 else state.current_section.content
    print(f"Finalizing section '{section_title}' with content preview: {section_content_preview}")
    logging.info(f"Finalizing section '{section_title}' with content length: {len(state.current_section.content)} characters")
    
    # Mark the section as finalized
    state.current_section.status = "approved"
    print(f"Section '{section_title}' marked as approved")
    
    # Ensure the section is properly stored in the sections list
    if state.current_section not in state.sections:
        print(f"Warning: Current section '{section_title}' not found in sections list. Adding it now.")
        state.sections.append(state.current_section)
    
    # Reset iteration count for next section
    state.iteration_count = 0
    print("Reset iteration count to 0 for next section")
    
    return state

async def transition_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates transitions between sections."""
    logging.info("Executing node: transition_generator")
    print(f"Transition generator - Current section index: {state.current_section_index}, Total sections: {len(state.outline.sections)}")
    
    # If we've just finalized a section and there's another section coming up
    if (state.current_section_index < len(state.outline.sections) and 
        state.current_section_index > 0 and 
        len(state.sections) > 0):
        
        current_section = state.sections[-1]
        next_section_title = state.outline.sections[state.current_section_index].title
        
        print(f"Transition generator - Moving from '{current_section.title}' to '{next_section_title}'")
        logging.info(f"Generating transition from '{current_section.title}' to '{next_section_title}'")
        
        # Get the last 200 characters of the current section
        current_section_ending = current_section.content[-200:] if len(state.current_section.content) > 200 else current_section.content
        
        # Prepare input variables for the prompt
        input_variables = {
            "current_section_title": current_section.title,
            "current_section_ending": current_section_ending,
            "next_section_title": next_section_title
        }
        
        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["section_transition"]["prompt"].format(**input_variables)
        
        try:
            response = await state.model.ainvoke(prompt)
            
            # Log the response content
            logging.info(f"\n\nTransition generation response from {current_section.title} to {next_section_title}:\n{response.content}\n\n")
            
            # Store the transition
            state.transitions[f"{current_section.title}_to_{next_section_title}"] = response.content
            
            print(f"Successfully generated transition from '{current_section.title}' to '{next_section_title}'")
            print(f"Next section to generate: '{next_section_title}'")
            
        except Exception as e:
            logging.error(f"Error generating transition: {e}")
            state.errors.append(f"Transition generation failed: {str(e)}")
            print(f"Error generating transition: {e}")
    else:
        if state.current_section_index >= len(state.outline.sections):
            print("Transition generator - All sections have been generated, moving to blog compilation")
        else:
            print(f"Transition generator - No transition needed (first section or no sections yet)")
    
    return state

async def blog_compiler(state: BlogDraftState) -> BlogDraftState:
    """Compiles the final blog post."""
    logging.info("Executing node: blog_compiler")
    
    # Update generation stage
    state.generation_stage = "compiling"
    
    # Get blog metadata
    blog_title = state.outline.title
    difficulty_level = state.outline.difficulty_level
    prerequisites = state.outline.prerequisites
    
    # Get sections content
    sections_content = "\n\n".join([
        f"## {section.title}\n{section.content}"
        for section in state.sections
    ])
    
    # Get transitions
    transitions = "\n\n".join([
        f"{key}:\n{value}"
        for key, value in state.transitions.items()
    ])
    
    # Prepare input variables for the prompt
    input_variables = {
        "blog_title": blog_title,
        "difficulty_level": difficulty_level,
        "prerequisites": prerequisites,
        "sections_content": sections_content,
        "transitions": transitions
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["blog_compilation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        # Log the response content
        logging.info(f"\n\nBlog compilation response:\n{response.content}\n\n")
        
        # Store the final blog post
        state.final_blog_post = response.content
        
        # Update generation stage
        state.generation_stage = "completed"
        
    except Exception as e:
        logging.error(f"Error compiling blog: {e}")
        state.errors.append(f"Blog compilation failed: {str(e)}")
    
    return state
