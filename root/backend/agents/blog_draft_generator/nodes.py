import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity # Added for semantic similarity
from backend.agents.blog_draft_generator.state import BlogDraftState, DraftSection, ContentReference, CodeExample, SectionVersion, SectionFeedback, ImagePlaceholder
from backend.utils.blog_context import extract_blog_narrative_context, calculate_content_length, calculate_section_length_targets, get_length_priority
from backend.services.persona_service import PersonaService
from backend.agents.blog_draft_generator.prompts import PROMPT_CONFIGS, EXPERT_WRITING_PRINCIPLES
from backend.agents.blog_draft_generator.utils import (
    extract_code_blocks,
    format_content_references,
    extract_section_metrics,
    parse_json_safely,
    format_code_examples,
    generate_table_of_contents,
    build_hierarchical_structure,
    build_contextual_query,
    process_search_results,
    determine_content_category
)
from backend.services.vector_store_service import VectorStoreService
from backend.agents.cost_tracking_decorator import track_node_costs, track_iteration_costs
from backend.services.supabase_project_manager import MilestoneType, SectionStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_and_enforce_constraints(content: str, include_code: bool, section_title: str) -> str:
    """
    Validates content against section constraints and enforces them.
    Removes code blocks if include_code is False, but preserves markdown-wrapped content.
    """
    import re
    
    logger.debug(f"DEBUG: validate_and_enforce_constraints - Input content length: {len(content)}, include_code: {include_code}")
    
    if not content:
        logger.debug(f"DEBUG: validate_and_enforce_constraints - Empty content received for section '{section_title}'")
        return content
    
    # First, handle the case where LLM wraps content in markdown fences
    # Pattern: ```markdown\n<content>\n```
    markdown_wrapper_pattern = r'```markdown\s*\n([\s\S]*?)\n\s*```'
    markdown_match = re.match(markdown_wrapper_pattern, content.strip(), re.DOTALL)
    
    if markdown_match:
        logger.debug(f"DEBUG: Found markdown-wrapped content, extracting inner content")
        content = markdown_match.group(1).strip()
        logger.debug(f"DEBUG: After markdown extraction, content length: {len(content)}")
        
    if not include_code:
        # More specific pattern that excludes markdown language specifiers
        # This pattern matches code blocks but not ```markdown wrappers
        code_block_pattern = r'```(?!markdown\s*\n)[\w]*\s*\n[\s\S]*?\n```'
        
        # Find all code blocks before removal for logging
        code_blocks = re.findall(code_block_pattern, content)
        if code_blocks:
            logging.warning(f"Section '{section_title}' has include_code=False but contains {len(code_blocks)} code block(s). Removing them.")
            logger.debug(f"DEBUG: Found {len(code_blocks)} actual code blocks to remove")
            for i, block in enumerate(code_blocks):
                logging.info(f"Removed code block {i+1}: {block[:100]}...")
        else:
            logger.debug(f"DEBUG: No actual code blocks found to remove")
        
        # Remove code blocks
        cleaned_content = re.sub(code_block_pattern, '', content)
        
        # Clean up any extra whitespace left after removal
        cleaned_content = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_content)
        
        result = cleaned_content.strip()
        logger.debug(f"DEBUG: validate_and_enforce_constraints - After code removal, content length: {len(result)}")
        return result
    
    logger.debug(f"DEBUG: validate_and_enforce_constraints - No constraints applied, returning original content")
    return content

@track_node_costs("semantic_mapper", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def semantic_content_mapper(state: BlogDraftState) -> BlogDraftState:
    """Maps content to sections using vector search for semantic matching with section headers."""
    logging.info("Executing node: semantic_content_mapper")
    
    # Initialize vector store service
    vector_store = VectorStoreService()
    # Get the embedding function instance from the service
    embedding_fn = getattr(vector_store, 'embedding_fn', None)
    if not embedding_fn:
        # Log a more critical error or raise if embeddings are essential
        logging.error("Embedding function not found in VectorStoreService. Semantic header matching will fail or be basic.")
        # Depending on requirements, could raise ValueError here

    content_mapping = {}

    # Set generation stage
    state.generation_stage = "mapping"
    
    # Extract section headers from markdown metadata
    section_headers = []
    if (state.markdown_content and 
        hasattr(state.markdown_content, 'metadata') and 
        state.markdown_content.metadata and 
        'section_headers' in state.markdown_content.metadata):
        
        section_headers = json.loads(state.markdown_content.metadata['section_headers'])
        logging.info(f"Found {len(section_headers)} section headers in markdown metadata")
        
        # Add position information if not present
        for i, header in enumerate(section_headers):
            if 'position' not in header:
                header['position'] = i
    
    # Build hierarchical structure from headers
    document_structure = build_hierarchical_structure(section_headers)
    logging.info(f"Built hierarchical document structure with {len(document_structure)} nodes")
    
    # For each section in the outline, use vector search with contextual awareness
    for section in state.outline.sections:
        section_title = section.title
        learning_goals = section.learning_goals
        
        logging.info(f"Processing section: {section_title}")
        
        # Find semantically relevant headers
        relevant_headers = []
        # The following 'if section_headers:' was causing indentation errors.
        # The conditions are handled within the enhanced matching block below.
        # Removing the outer if statement.
        # --- Enhanced Semantic Header Matching using Embeddings ---
        if section_headers and embedding_fn: # Check if we have headers and the function
            try:
                # Prepare texts for embedding
                target_text = f"{section_title} - {' '.join(learning_goals)}"
                header_texts = [h.get('text', '') for h in section_headers]

                # Generate embeddings using the embedding function directly
                # Call with a list for single item, then extract the first embedding
                # Assuming embedding_fn is async, add await
                target_embedding_list = await embedding_fn([target_text])
                if not target_embedding_list:
                     raise ValueError("Embedding function returned empty list for target text.")
                target_embedding = target_embedding_list[0]

                # Call with the list of header texts
                # Assuming embedding_fn is async, add await
                header_embeddings = await embedding_fn(header_texts)
                if len(header_embeddings) != len(header_texts):
                    raise ValueError(f"Embedding function returned {len(header_embeddings)} embeddings for {len(header_texts)} header texts.")

                # Calculate cosine similarity (needs embeddings in correct shape)
                # Ensure target_embedding is 2D for cosine_similarity
                similarities = cosine_similarity([target_embedding], header_embeddings)[0]

                # Create relevant_headers list with similarity scores
                similarity_threshold = 0.6 # Adjust this threshold as needed
                for header, sim in zip(section_headers, similarities):
                    if sim >= similarity_threshold:
                        relevant_headers.append({
                            'text': header.get('text', ''),
                            'level': header.get('level', 1),
                            'similarity': float(sim) # Ensure it's a float
                        })

                # Sort by similarity
                relevant_headers.sort(key=lambda x: x.get('similarity', 0), reverse=True)
                logging.info(f"Found {len(relevant_headers)} semantically relevant headers (threshold > {similarity_threshold}) for section '{section_title}' using embeddings.")

            except Exception as e:
                logging.error(f"Error during semantic header matching for section '{section_title}': {e}. Falling back to basic text overlap.")
                # Fallback to basic text overlap if embedding fails
                relevant_headers = [] # Reset before fallback
                for header in section_headers:
                    header_text = header.get('text', '').lower()
                    section_text = section_title.lower()
                    if (header_text in section_text or section_text in header_text or any(goal.lower() in header_text for goal in learning_goals)):
                        relevant_headers.append({ 'text': header.get('text', ''), 'level': header.get('level', 1), 'similarity': 0.5 }) # Assign lower default similarity
                relevant_headers.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        elif section_headers: # Fallback if embedding function is missing but headers exist
            logging.warning(f"No embedding function available for semantic matching for section '{section_title}'. Using basic text overlap.")
            for header in section_headers:
                header_text = header.get('text', '').lower()
                section_text = section_title.lower()
                if (header_text in section_text or section_text in header_text or any(goal.lower() in header_text for goal in learning_goals)):
                    relevant_headers.append({ 'text': header.get('text', ''), 'level': header.get('level', 1), 'similarity': 0.5 })
            relevant_headers.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        # --- End of Enhanced Matching ---
        
        # Build contextual query with header hierarchy awareness
        if relevant_headers:
            contextual_query = build_contextual_query(
                section_title,
                learning_goals,
                relevant_headers,
                document_structure
            )
            logging.info(f"Enhanced query with structural context: {contextual_query}")
        else:
            # Fallback to basic query if no relevant headers found
            contextual_query = f"{section_title}: {', '.join(learning_goals)}"
            logging.info(f"Using basic query (no relevant headers): {contextual_query}")
        
        # Perform vector search with enhanced query
        markdown_results = vector_store.search_content(
            query=contextual_query,
            metadata_filter={"source_type": "markdown"},
            n_results=15
        )
        
        # Search for code examples
        code_results = vector_store.search_content(
            query=contextual_query,
            metadata_filter={"source_type": "code"},
            n_results=10
        )
        
        # Process search results with structural awareness
        references = []
        
        # Process markdown results with structural awareness
        if markdown_results:
            markdown_references = process_search_results(
                markdown_results,
                relevant_headers,
                document_structure
            )
            references.extend(markdown_references)
        
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
        
        # Use LLM to validate and enhance the content mapping with structural awareness
        if references:
            # Format headers for context
            formatted_headers = ""
            if relevant_headers:
                formatted_headers = "\n".join([
                    f"{'#' * h['level']} {h['text']} (Similarity: {h.get('similarity', 0):.2f})"
                    for h in relevant_headers[:5]
                ])
            
            # Take top 10 references for LLM validation
            top_references = references[:10]
            formatted_references = "\n\n".join([
                f"Content: {ref.content[:300]}...\n"
                f"Type: {ref.source_type}\n"
                f"Relevance: {ref.relevance_score}\n"
                f"Category: {ref.category}\n"
                f"Structural Context: {ref.structural_context if ref.structural_context else 'None'}"
                for ref in top_references
            ])
            
            # Prepare input variables for the prompt
            input_variables = {
                "format_instructions": PROMPT_CONFIGS["content_validation"]["parser"].get_format_instructions(),
                "section_title": section_title,
                "learning_goals": ", ".join(learning_goals),
                "relevant_headers": formatted_headers,
                "content_references": formatted_references
            }
            
            # Format prompt and get LLM response
            prompt = PROMPT_CONFIGS["content_validation"]["prompt"].format(**input_variables)
            
            try:
                response = await state.model.ainvoke(prompt)
                response = response if isinstance(response, str) else response.content
                
                logging.info(f"\n\nContent validation response for section {section_title}:\n{response}\n\n")
                
                # Parse the response to get validated references
                validated_items = parse_json_safely(response, [])
                
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
                                    source_location=ref.source_location,
                                    structural_context=ref.structural_context
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

# --- New HyDE Nodes ---

@track_node_costs("generate_hypothetical_document", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def generate_hypothetical_document(state: BlogDraftState) -> BlogDraftState:
    """Generates a hypothetical document/answer for the current section to improve retrieval."""
    logging.info("Executing node: generate_hypothetical_document")
    if state.current_section is None:
        logging.warning("No current section to generate hypothetical document for.")
        state.errors.append("Cannot generate hypothetical document without a current section.")
        return state

    section_title = state.current_section.title
    # Find the corresponding section in the outline to get learning goals
    outline_section = next((s for s in state.outline.sections if s.title == section_title), None)
    learning_goals = outline_section.learning_goals if outline_section else []

    logging.info(f"Generating hypothetical document for section: '{section_title}'")

    # Prepare prompt input
    input_vars = {
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals)
    }

    # Check if the prompt exists in config
    if "hyde_generation" not in PROMPT_CONFIGS:
        logging.error("HyDE generation prompt configuration not found in PROMPT_CONFIGS.")
        state.errors.append("Missing HyDE prompt configuration.")
        # Fallback: Use a simple query string if prompt is missing
        state.hypothetical_document = f"{section_title}: {', '.join(learning_goals)}"
        logging.warning(f"Using fallback query for HyDE due to missing prompt: {state.hypothetical_document}")
        return state

    # Format prompt and invoke LLM
    try:
        prompt = PROMPT_CONFIGS["hyde_generation"]["prompt"].format(**input_vars)
        response = await state.model.ainvoke(prompt)
        hypothetical_doc = response if isinstance(response, str) else response.content

        state.hypothetical_document = hypothetical_doc
        logging.info(f"Generated hypothetical document (length: {len(hypothetical_doc)}): {hypothetical_doc[:150]}...")

    except Exception as e:
        logging.exception(f"Error generating hypothetical document for section '{section_title}': {e}")
        state.errors.append(f"HyDE generation failed: {str(e)}")
        # Fallback: Use a simple query string on error
        state.hypothetical_document = f"{section_title}: {', '.join(learning_goals)}"
        logging.warning(f"Using fallback query for HyDE due to error: {state.hypothetical_document}")

    return state

@track_node_costs("retrieve_context_with_hyde", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def retrieve_context_with_hyde(state: BlogDraftState) -> BlogDraftState:
    """Retrieves context from vector store using the generated hypothetical document."""
    logging.info("Executing node: retrieve_context_with_hyde")
    if not state.hypothetical_document:
        logging.warning("No hypothetical document generated, skipping HyDE retrieval.")
        # Decide if this should be an error or if we proceed without HyDE context
        # For now, let's allow proceeding, section_generator might handle missing context
        state.hyde_retrieved_context = []
        return state

    try:
        # Initialize vector store service (consider passing it via state if needed frequently)
        vector_store = VectorStoreService()
        project_name = state.project_name # Get project name directly from state

        logging.info(f"Retrieving context using HyDE query (length: {len(state.hypothetical_document)}): {state.hypothetical_document[:150]}...")

        # Perform vector search using the hypothetical document as the query
        # Combine markdown and code results? Or keep separate? Let's combine for now.
        # Adjust n_results as needed
        retrieved_docs = vector_store.search_content(
            query=state.hypothetical_document,
            metadata_filter={"project_name": project_name}, # Filter by project
            n_results=15 # Retrieve a decent number of chunks
        )

        # Store the raw results (list of dicts) in the state
        state.hyde_retrieved_context = retrieved_docs
        logging.info(f"Retrieved {len(retrieved_docs)} context chunks using HyDE.")

        # Optional: Log retrieved content snippets for debugging
        # for i, doc in enumerate(retrieved_docs[:3]):
        #     logging.debug(f"  HyDE Result {i+1} (Relevance: {doc.get('relevance', 0):.2f}): {doc.get('content', '')[:100]}...")

    except Exception as e:
        logging.exception(f"Error retrieving context with HyDE: {e}")
        state.errors.append(f"HyDE retrieval failed: {str(e)}")
        state.hyde_retrieved_context = [] # Ensure it's an empty list on error

    return state

# --- End New HyDE Nodes ---


@track_node_costs("generator", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def section_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates content for current section using retrieved HyDE context."""
    logging.info("Executing node: section_generator")
    logger.debug(f"Section generator - Starting generation for section index {state.current_section_index}")
    
    # Update generation stage
    state.generation_stage = "drafting"
    
    if state.current_section_index >= len(state.outline.sections):
        logging.info("All sections have been generated.")
        logger.debug("All sections have been generated.")
        return state
    
    section = state.outline.sections[state.current_section_index]
    section_title = section.title
    learning_goals = section.learning_goals
    
    logger.debug(f"Section generator - Generating content for '{section_title}' using HyDE context")

    # Get relevant context retrieved via HyDE
    hyde_context_list = state.hyde_retrieved_context if state.hyde_retrieved_context else []
    logging.info(f"Using {len(hyde_context_list)} context chunks retrieved via HyDE.")

    # Format the HyDE context for the prompt (e.g., top 5 chunks)
    # Each item in hyde_context_list is a dict like {'content': '...', 'metadata': {...}, 'relevance': ...}
    formatted_hyde_context = "\n\n---\n\n".join([
        f"Retrieved Context (Relevance: {ctx.get('relevance', 0):.2f}):\n{ctx.get('content', '')}"
        for ctx in hyde_context_list[:5] # Limit context length for prompt
    ])

    if not formatted_hyde_context:
        logging.warning(f"No context retrieved via HyDE for section '{section_title}'. Generation quality may be affected.")
        formatted_hyde_context = "No specific context was retrieved. Please generate the section based on the title and learning goals."

    # --- The following logic for original structure/insights might be less relevant now,
    # --- or could be adapted to use metadata from hyde_retrieved_context if needed.
    # --- For now, let's simplify and focus on using the HyDE context directly. ---

    # Extract section headers from markdown metadata (Keep for potential future use)
    section_headers = []
    if (state.markdown_content and 
        hasattr(state.markdown_content, 'metadata') and 
        state.markdown_content.metadata and 
        'section_headers' in state.markdown_content.metadata):
        
        section_headers = json.loads(state.markdown_content.metadata['section_headers'])
    
    # Find relevant headers for this section
    relevant_headers = []
    if section_headers:
        # Simple semantic matching for headers
        for header in section_headers:
            header_text = header.get('text', '').lower()
            section_text = section_title.lower()
            
            # Check for text overlap or containment
            if (header_text in section_text or 
                section_text in header_text or 
                any(goal.lower() in header_text for goal in learning_goals)):
                
                relevant_headers.append(header)
    
    # Format headers for the prompt
    original_structure = ""
    if relevant_headers:
        original_structure = "Original document structure:\n"
        # Sort by position or level
        sorted_headers = sorted(relevant_headers, key=lambda h: h.get('position', h.get('level', 1)))
        for header in sorted_headers:
            level = header.get('level', 1)
            text = header.get('text', '')
            indent = "  " * (level - 1)
            original_structure += f"{indent}{'#' * level} {text}\n"

    # Get enhanced previous section content for context if available
    previous_context = ""
    if state.current_section_index > 0 and state.sections:
        prev_section = state.sections[-1]
        
        # Get previous section ending (last paragraph or 200 chars)
        prev_ending = ""
        if prev_section.content:
            # Try to get last paragraph
            paragraphs = prev_section.content.split('\n\n')
            if len(paragraphs) > 1:
                prev_ending = paragraphs[-1]
            else:
                # Fallback to last 200 characters
                prev_ending = prev_section.content[-200:] if len(prev_section.content) > 200 else prev_section.content
        
        # Get upcoming sections preview
        upcoming_sections = []
        if hasattr(state.outline, 'sections') and state.outline.sections:
            start_idx = state.current_section_index
            end_idx = min(start_idx + 2, len(state.outline.sections))
            upcoming_sections = [
                state.outline.sections[i].title 
                for i in range(start_idx, end_idx)
            ]
        
        # Build enhanced context
        previous_context = f"""
BLOG PROGRESSION CONTEXT:
Blog Title: {getattr(state.outline, 'title', 'Untitled Blog')}
Completed Sections: {[s.title for s in state.sections]}
Previous Section: {prev_section.title}
Key Concepts Covered: {', '.join(getattr(prev_section, 'key_concepts', [])) if hasattr(prev_section, 'key_concepts') and prev_section.key_concepts else 'N/A'}
Previous Section Ending: {prev_ending}
Upcoming Sections: {upcoming_sections}
Current Position: Section {state.current_section_index + 1} of {len(getattr(state.outline, 'sections', []))}
        """
    else:
        previous_context = "BLOG PROGRESSION CONTEXT:\nThis is the first section of the blog."
    
    # Extract structural context from content references
    structural_insights = ""
    if relevant_headers:
        # Find references with structural context
        structured_refs = [ref for ref in relevant_headers if ref.structural_context]
        if structured_refs:
            structural_insights = "Structural insights from content analysis:\n"
            for ref in structured_refs[:3]:  # Limit to top 3
                if ref.structural_context:
                    structural_insights += f"- Content related to: {list(ref.structural_context.keys())}\n"
                    for header, context in ref.structural_context.items():
                        if context.get('parent'):
                            structural_insights += f"  - Parent topic: {context.get('parent')}\n"
                        if context.get('children'):
                            structural_insights += f"  - Related subtopics: {', '.join(context.get('children')[:3])}\n"

    # Initialize persona service and get persona instructions
    persona_service = PersonaService()
    # Get persona from state, with fallback to neuraforge
    persona_name = getattr(state, 'persona', 'neuraforge')
    persona_instructions = persona_service.get_persona_prompt(persona_name)

    # Log which persona is being used
    logger.info(f"Using persona: {persona_name} for section generation")
    
    # Extract blog narrative context
    blog_narrative_context = extract_blog_narrative_context(state)
    
    # Calculate length constraints
    current_blog_length = sum(calculate_content_length(section.content) for section in state.sections)
    
    # Calculate section length targets if not already done
    if not state.section_length_targets:
        state.section_length_targets = calculate_section_length_targets(state.outline, state.target_total_length)
    
    target_section_length = state.section_length_targets.get(section_title, 500)  # Default to 500 words
    remaining_length_budget = max(state.target_total_length - current_blog_length, 0)
    length_priority = get_length_priority(current_blog_length, target_section_length, remaining_length_budget)
    
    # Update state with current calculations
    state.current_total_length = current_blog_length
    state.remaining_length_budget = remaining_length_budget
    
    # Prepare input variables for the prompt, using formatted_hyde_context
    input_variables = {
        "persona_instructions": persona_instructions,
        "expert_writing_principles": EXPERT_WRITING_PRINCIPLES,
        "format_instructions": PROMPT_CONFIGS["section_generation"]["parser"].get_format_instructions() if PROMPT_CONFIGS["section_generation"]["parser"] else "",
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "formatted_content": formatted_hyde_context, # Use HyDE context here
        "previous_context": previous_context,
        "blog_narrative_context": blog_narrative_context,
        "target_section_length": target_section_length,
        "current_blog_length": current_blog_length,
        "remaining_length_budget": remaining_length_budget,
        "length_priority": length_priority,
        # Keep original_structure and structural_insights for now, though their relevance might decrease
        "original_structure": original_structure,
        "structural_insights": structural_insights,
        "current_section_data": json.dumps(section.model_dump()) # Pass the current section data (including constraints) as JSON string
    }

    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["section_generation"]["prompt"].format(**input_variables)
    
    try:
        llm_output_str = await state.model.ainvoke(prompt)
        llm_output_str = llm_output_str if isinstance(llm_output_str, str) else llm_output_str.content
        
        logging.info(f"\n\nRaw LLM output for section {section_title}:\n{llm_output_str}\n\n")

        actual_markdown_content = ""
        parsed_title = section_title # Default to outline title
        
        try:
            # The prompt instructs the LLM to return a DraftSection JSON.
            # PROMPT_CONFIGS["section_generation"]["parser"] is PydanticOutputParser(pydantic_object=DraftSection)
            parsed_draft_section_object = PROMPT_CONFIGS["section_generation"]["parser"].parse(llm_output_str)
            actual_markdown_content = parsed_draft_section_object.content
            # Optionally, update title if LLM refines it, though prompt doesn't explicitly ask for this.
            # parsed_title = parsed_draft_section_object.title 
            logging.info(f"Successfully parsed DraftSection. Extracted content length: {len(actual_markdown_content)}")
            logger.debug(f"DEBUG: Successfully parsed DraftSection content length: {len(actual_markdown_content)}")
        except Exception as e:
            logging.error(f"Failed to parse DraftSection from LLM output for section '{section_title}': {e}. LLM output was: {llm_output_str}")
            logger.debug(f"DEBUG: Failed to parse DraftSection, attempting fallback. Error: {e}")
            # Fallback: Try to extract content if LLM just returned markdown, or use error message.
            # This might happen if the LLM doesn't perfectly follow the JSON instruction.
            if "{" not in llm_output_str and "}" not in llm_output_str: # Heuristic: if no JSON structure, assume it's direct markdown
                actual_markdown_content = llm_output_str
                logging.warning("LLM output did not seem to be JSON, using raw output as content.")
                logger.debug(f"DEBUG: Using raw output as content. Length: {len(actual_markdown_content)}")
            else:
                actual_markdown_content = f"Error: Could not parse section content from LLM. Raw output: {llm_output_str}"
                logger.debug(f"DEBUG: Using error fallback content. Length: {len(actual_markdown_content)}")
        
        logger.debug(f"DEBUG: Before validation - actual_markdown_content length: {len(actual_markdown_content)}")
        
        # Create a new draft section
        draft_section = DraftSection(
            title=parsed_title, # Use title from outline or potentially parsed one
            content=actual_markdown_content, # Assign the extracted Markdown string
            feedback=[],
            versions=[],
            current_version=1,
            status="draft"
        )
        
        # Extract key concepts and technical terms
        # This could be enhanced with NLP in a future version
        draft_section.key_concepts = learning_goals
        
        # Validate and enforce constraints on the generated content
        logger.debug(f"DEBUG: Section '{section_title}' include_code: {section.include_code}")
        validated_content = validate_and_enforce_constraints(
            actual_markdown_content, 
            section.include_code, 
            section_title
        )
        logger.debug(f"DEBUG: After validation - content length: {len(validated_content)}")
        draft_section.content = validated_content
        logger.debug(f"DEBUG: Final draft section content length: {len(draft_section.content)}")
        
        # Add to sections list
        state.sections.append(draft_section)
        state.current_section = draft_section
        # Note: current_section_index will be incremented in section_finalizer after completion
        
    except Exception as e:
        logging.error(f"Error generating section: {e}")
        state.errors.append(f"Section generation failed: {str(e)}")
        return state
    
    return state

@track_node_costs("enhancer", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def content_enhancer(state: BlogDraftState) -> BlogDraftState:
    """Enhances section content while maintaining original document structure."""
    logging.info("Executing node: content_enhancer")
    
    # Update generation stage
    state.generation_stage = "enhancing"
    
    if state.current_section is None:
        logging.warning("No current section to enhance.")
        return state
    
    section_title = state.current_section.title
    section_index = state.current_section_index  # Use current index directly (0-based)
    learning_goals = state.outline.sections[section_index].learning_goals
    relevant_content = state.content_mapping.get(section_title, [])
    existing_content = state.current_section.content
    
    # Extract section headers from markdown metadata
    section_headers = []
    if (state.markdown_content and 
        hasattr(state.markdown_content, 'metadata') and 
        state.markdown_content.metadata and 
        'section_headers' in state.markdown_content.metadata):
        
        section_headers = json.loads(state.markdown_content.metadata['section_headers'])
    
    # Find relevant headers for this section
    relevant_headers = []
    if section_headers:
        # Simple semantic matching for headers
        for header in section_headers:
            header_text = header.get('text', '').lower()
            section_text = section_title.lower()
            
            # Check for text overlap or containment
            if (header_text in section_text or 
                section_text in header_text or 
                any(goal.lower() in header_text for goal in learning_goals)):
                
                relevant_headers.append(header)
    
    # Format headers for the prompt
    original_structure = ""
    if relevant_headers:
        original_structure = "Original document structure:\n"
        # Sort by position or level
        sorted_headers = sorted(relevant_headers, key=lambda h: h.get('position', h.get('level', 1)))
        for header in sorted_headers:
            level = header.get('level', 1)
            text = header.get('text', '')
            indent = "  " * (level - 1)
            original_structure += f"{indent}{'#' * level} {text}\n"
    
    # Format content for the prompt using utility function
    # Only use high-relevance content for enhancement
    high_relevance_content = [ref for ref in relevant_content if ref.relevance_score > 0.5]
    formatted_content = format_content_references(high_relevance_content)
    
    # Extract structural context from content references
    structural_insights = ""
    if high_relevance_content:
        # Find references with structural context
        structured_refs = [ref for ref in high_relevance_content if ref.structural_context]
        if structured_refs:
            structural_insights = "Structural insights from content analysis:\n"
            for ref in structured_refs[:3]:  # Limit to top 3
                if ref.structural_context:
                    structural_insights += f"- Content related to: {list(ref.structural_context.keys())}\n"
                    for header, context in ref.structural_context.items():
                        if context.get('parent'):
                            structural_insights += f"  - Parent topic: {context.get('parent')}\n"
                        if context.get('children'):
                            structural_insights += f"  - Related subtopics: {', '.join(context.get('children')[:3])}\n"
    
    # Get current section constraints from outline
    section = state.outline.sections[section_index]
    
    # Prepare input variables for the prompt
    input_variables = {
        "format_instructions": PROMPT_CONFIGS["content_enhancement"]["parser"].get_format_instructions() if PROMPT_CONFIGS["content_enhancement"]["parser"] else "",
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "existing_content": existing_content,
        "formatted_content": formatted_content,
        "original_structure": original_structure,
        "structural_insights": structural_insights,
        "current_section_data": json.dumps(section.model_dump())  # Pass section constraints including include_code
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["content_enhancement"]["prompt"].format(**input_variables)
    
    try:
        llm_response_str = await state.model.ainvoke(prompt)
        llm_response_str = llm_response_str if isinstance(llm_response_str, str) else llm_response_str.content
        
        logging.info(f"\n\nRaw LLM content enhancement response for {section_title}:\n{llm_response_str}\n\n")

        processed_content = llm_response_str # Default to the full response

        # Attempt to find and parse a JSON block if the LLM unexpectedly returns one
        # (though this node's prompt asks for direct Markdown)
        json_match = re.search(r'\{.*\}', llm_response_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                # Try to parse it as if it's a DraftSection or similar structure
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, dict) and "content" in parsed_json and isinstance(parsed_json["content"], str):
                    processed_content = parsed_json["content"]
                    logging.info(f"Extracted 'content' field from unexpected JSON in content_enhancer response.")
                else:
                    logging.warning("Found JSON in content_enhancer response, but it did not match expected structure (e.g., missing 'content' field). Using full response minus preamble if any.")
                    if llm_response_str.strip().startswith("{"):
                        processed_content = json_str
                    else:
                         lines = llm_response_str.splitlines()
                         json_start_line = -1
                         for i, line in enumerate(lines):
                             if line.strip().startswith("{"):
                                 json_start_line = i
                                 break
                         if json_start_line != -1:
                             logging.info("Stripping preamble before JSON object in content_enhancer.")
                             processed_content = "\n".join(lines[json_start_line:])
            except json.JSONDecodeError:
                logging.warning(f"Could not parse JSON found in content_enhancer response. Using full response. JSON part: {json_str}")

        # Store the original content as a version
        state.current_section.versions.append(SectionVersion(
            content=state.current_section.content, # Old content
            version_number=state.current_section.current_version,
            timestamp=datetime.now().isoformat(),
            changes="Initial enhancement"
        ))
        
        # Validate and enforce constraints
        validated_content = validate_and_enforce_constraints(
            processed_content, 
            section.include_code, 
            section_title
        )
        
        # Update the section content
        state.current_section.content = validated_content
        state.current_section.current_version += 1
        
    except Exception as e:
        logging.error(f"Error enhancing section: {e}")
        state.errors.append(f"Section enhancement failed: {str(e)}")
        return state
    
    return state

@track_node_costs("code_extractor", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
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
            
            response = response if isinstance(response, str) else response.content
            
            # Log the response content
            logging.info(f"\n\nCode example extraction response for example {i+1}:\n{response}\n\n")
            
            # Parse the response
            result = parse_json_safely(response, {})
            
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

@track_node_costs("image_placeholder", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def image_placeholder_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates strategic image placeholders for enhanced content visualization."""
    logging.info("Executing node: image_placeholder_generator")
    
    if state.current_section is None:
        logging.warning("No current section to generate image placeholders for.")
        return state
    
    section_title = state.current_section.title
    section_index = state.current_section_index
    section_content = state.current_section.content
    learning_goals = state.outline.sections[section_index].learning_goals
    
    # Analyze content characteristics
    content_length = len(section_content.split())
    has_code_examples = bool(state.current_section.code_examples) or "```" in section_content
    
    # Determine content type based on section analysis
    content_type = "practical" if has_code_examples else "theoretical"
    if "algorithm" in section_content.lower() or "process" in section_content.lower():
        content_type = "process-oriented"
    elif "architecture" in section_content.lower() or "system" in section_content.lower():
        content_type = "architectural"
    
    # Assess complexity level
    complexity_indicators = ["implementation", "advanced", "complex", "detailed", "architecture"]
    complexity_level = "high" if any(indicator in section_content.lower() for indicator in complexity_indicators) else "medium"
    
    # Extract main concepts from learning goals and content
    main_concepts = learning_goals[:3]  # Use first 3 learning goals as main concepts

    try:
        # Prepare input variables for the prompt
        input_variables = {
            "format_instructions": PROMPT_CONFIGS["image_placeholder"]["parser"].get_format_instructions(),
            "section_title": section_title,
            "learning_goals": ", ".join(learning_goals),
            "content_type": content_type,
            "has_code_examples": str(has_code_examples),
            "section_content": section_content,
            "content_length": str(content_length),
            "complexity_level": complexity_level,
            "main_concepts": ", ".join(main_concepts),
        }
        
        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["image_placeholder"]["prompt"].format(**input_variables)
        
        llm_response = await state.model.ainvoke(prompt)
        llm_response_str = llm_response if isinstance(llm_response, str) else llm_response.content
        
        logging.info(f"\n\nRaw LLM image placeholder response for {section_title}:\n{llm_response_str}\n\n")
        
        # Parse the response
        try:
            if llm_response_str.strip():
                image_placeholder = PROMPT_CONFIGS["image_placeholder"]["parser"].parse(llm_response_str)
                
                # Validate the parsed result
                if isinstance(image_placeholder, ImagePlaceholder) and image_placeholder.description.strip():
                    state.current_section.image_placeholders = [image_placeholder]
                    logging.info(f"Generated image placeholder for section '{section_title}': {image_placeholder.type}")
                else:
                    logging.info(f"No meaningful image placeholder suggested for section '{section_title}'")
            else:
                logging.info(f"LLM returned empty response for image placeholder generation in section '{section_title}'")
                
        except Exception as parse_error:
            logging.warning(f"Failed to parse image placeholder response for '{section_title}': {parse_error}")
            logging.info("Continuing without image placeholders for this section.")
    
    except Exception as e:
        logging.error(f"Error generating image placeholders for section '{section_title}': {e}")
        # Continue without image placeholders rather than failing the entire section
        
    return state

@track_node_costs("validator", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
@track_iteration_costs
async def quality_validator(state: BlogDraftState) -> BlogDraftState:
    """Validates the quality of the current section with comprehensive scoring."""
    logging.info("Executing node: quality_validator")
    logger.debug(f"Quality validator - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    logging.info(f"Quality validator - Current section index: {state.current_section_index}, Section: {state.current_section.title if state.current_section else 'None'}")

    # Update generation stage
    state.generation_stage = "validating"

    if state.current_section is None:
        logging.warning("No current section to validate.")
        return state

    section_title = state.current_section.title
    section_index = state.current_section_index
    learning_goals = state.outline.sections[section_index].learning_goals
    section_content = state.current_section.content

    # NEW: Get persona profile and structural rules
    from backend.services.persona_service import PersonaService
    from backend.agents.blog_draft_generator.prompts import get_structural_rules
    persona_service = PersonaService()
    persona_name = getattr(state, 'persona', 'neuraforge')
    persona_profile = persona_service.get_persona_prompt(persona_name)

    # NEW: Get structural rules based on post type
    post_type = getattr(state, 'post_type', 'default')
    structural_rules = get_structural_rules(post_type)

    # NEW: Get target length for this section
    target_length = state.section_length_targets.get(section_title, 400)

    # Check if we should use comprehensive validation (when persona and structural rules are available)
    use_comprehensive = True  # Always use comprehensive validation for better quality

    if use_comprehensive:
        # Prepare input variables for the comprehensive prompt
        input_variables = {
            "section_title": section_title,
            "learning_goals": ", ".join(learning_goals),
            "section_content": section_content,
            "persona_name": persona_name,
            "persona_profile": persona_profile,
            "structural_rules": structural_rules,
            "target_length": target_length
        }

        # Use the comprehensive validation prompt
        prompt = PROMPT_CONFIGS["comprehensive_quality_validation"]["prompt"].format(**input_variables)
    else:
        # Fallback to original validation (backward compatibility)
        input_variables = {
            "section_title": section_title,
            "learning_goals": ", ".join(learning_goals),
            "section_content": section_content
        }
        prompt = PROMPT_CONFIGS["quality_validation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        response = response if isinstance(response, str) else response.content
        
        # Log the response content
        logging.info(f"\n\nQuality validation response for {section_title}:\n{response}\n\n")
        
        # Parse the response
        parsed_result = parse_json_safely(response, {})
        logging.info(f"Parsed quality validation result")

        if use_comprehensive:
            # Handle comprehensive validation response
            if not parsed_result:
                logging.warning(f"Comprehensive validation response was not valid JSON")
                # Set default low scores for all metrics
                parsed_result = {
                    # Content quality metrics
                    "completeness": 0.0, "technical_accuracy": 0.0, "clarity": 0.0,
                    "code_quality": 0.0, "engagement": 0.0, "structural_consistency": 0.0,
                    # Persona compliance metrics
                    "voice_match": 0.0, "tone_consistency": 0.0,
                    "audience_alignment": 0.0, "style_adherence": 0.0,
                    # Structural compliance metrics
                    "heading_hierarchy": 0.0, "paragraph_flow": 0.0,
                    "length_compliance": 0.0, "list_usage": 0.0, "no_fragmentation": 0.0,
                    # Aggregated scores
                    "content_quality_score": 0.0,
                    "persona_compliance_score": 0.0,
                    "structural_compliance_score": 0.0,
                    "overall_score": 0.0,
                    "improvement_needed": True,
                    "content_issues": ["Failed to parse validation response"],
                    "persona_violations": [],
                    "structural_violations": [],
                    "improvement_suggestions": ["Regenerate section"]
                }

            # Store all metrics
            state.current_section.quality_metrics = {
                k: float(v) for k, v in parsed_result.items()
                if k not in ["improvement_needed", "content_issues",
                            "persona_violations", "structural_violations",
                            "improvement_suggestions"]
            }

            # Store detailed scores
            state.current_section.content_quality_score = parsed_result.get("content_quality_score", 0.0)
            state.current_section.persona_compliance_score = parsed_result.get("persona_compliance_score", 0.0)
            state.current_section.structural_compliance_score = parsed_result.get("structural_compliance_score", 0.0)

            # Store issues
            state.current_section.content_issues = parsed_result.get("content_issues", [])
            state.current_section.persona_violations = parsed_result.get("persona_violations", [])
            state.current_section.structural_violations = parsed_result.get("structural_violations", [])

            # Calculate weighted overall score if not provided
            if "overall_score" not in parsed_result or parsed_result["overall_score"] == 0.0:
                weights = state.quality_weights
                overall = (
                    weights['content'] * state.current_section.content_quality_score +
                    weights['persona'] * state.current_section.persona_compliance_score +
                    weights['structure'] * state.current_section.structural_compliance_score
                )
                state.current_section.quality_metrics["overall_score"] = overall
            else:
                overall = parsed_result["overall_score"]

            logger.debug(f"Comprehensive Scores - Content: {state.current_section.content_quality_score:.2f}, "
                  f"Persona: {state.current_section.persona_compliance_score:.2f}, "
                  f"Structure: {state.current_section.structural_compliance_score:.2f}, "
                  f"Overall: {overall:.2f}")

        else:
            # Original validation handling (backward compatibility)
            required_metrics = [
                "completeness", "technical_accuracy", "clarity",
                "code_quality", "engagement", "structural_consistency", "overall_score"
            ]
            quality_metrics = {}
            parsing_successful = True

            if not parsed_result:
                logging.warning(f"Quality validation LLM response for '{section_title}' was not valid JSON or was empty.")
                parsing_successful = False
            else:
                for metric in required_metrics:
                    if metric not in parsed_result or not isinstance(parsed_result[metric], (float, int)):
                        logging.warning(f"Metric '{metric}' missing or invalid type in quality validation response for '{section_title}'")
                        quality_metrics[metric] = 0.0
                    else:
                        quality_metrics[metric] = float(parsed_result[metric])

            # If parsing failed completely, assign all defaults
            if not parsing_successful:
                quality_metrics = {metric: 0.0 for metric in required_metrics}
                logging.info(f"Assigned default low scores for '{section_title}' due to parsing failure.")

            # Store quality metrics
            state.current_section.quality_metrics = quality_metrics
            overall = quality_metrics.get("overall_score", 0.0)

        # Determine if improvement is needed based on overall score
        overall_score = state.current_section.quality_metrics.get("overall_score", overall)
        quality_threshold = state.quality_threshold
        improvement_needed = overall_score < quality_threshold
        logger.debug(f"Overall score: {overall_score:.2f}, Quality Threshold: {quality_threshold}, Improvement needed: {improvement_needed}")

        # Increment iteration count
        state.iteration_count += 1
        logger.debug(f"Incremented iteration count to: {state.iteration_count}")
        
        # If improvement is needed and we haven't reached max iterations, continue
        if improvement_needed and state.iteration_count < state.max_iterations:
            logger.debug(f"Improvement needed and iteration count ({state.iteration_count}) < max iterations ({state.max_iterations})")
            state.status["current_section"] = f"Needs improvement (iteration {state.iteration_count})"
        else:
            # Section is good enough or we've reached max iterations
            logger.debug(f"Section is good enough or max iterations reached. Iteration count: {state.iteration_count}")
            state.status["current_section"] = "Ready for finalization"
            state.completed_sections.add(section_index)
            
    except Exception as e:
        logging.error(f"Error validating section quality: {e}")
        state.errors.append(f"Quality validation failed: {str(e)}")
        state.iteration_count += 1
        logger.debug(f"Error in quality validator. Incremented iteration count to: {state.iteration_count}")
    
    return state

@track_node_costs("auto_feedback", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def auto_feedback_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates automatic feedback based on comprehensive quality metrics."""
    logging.info("Executing node: auto_feedback_generator")
    logger.debug(f"Auto feedback generator - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")

    if state.current_section is None:
        logging.warning("No current section to generate feedback for.")
        logger.debug("No current section to generate feedback for.")
        return state

    feedback_points = []

    # Content quality feedback (using issues if available)
    if hasattr(state.current_section, 'content_issues') and state.current_section.content_issues:
        for issue in state.current_section.content_issues[:3]:  # Top 3 content issues
            feedback_points.append(f"Content: {issue}")
    else:
        # Fallback to metrics-based feedback
        quality_metrics = getattr(state.current_section, "quality_metrics", {})

        if quality_metrics.get("completeness", 1.0) < 0.8:
            feedback_points.append("Content: Ensure all learning goals are thoroughly covered")

        if quality_metrics.get("technical_accuracy", 1.0) < 0.8:
            feedback_points.append("Content: Verify technical accuracy and provide more precise explanations")

        if quality_metrics.get("clarity", 1.0) < 0.8:
            feedback_points.append("Content: Improve clarity by breaking down complex concepts")

        if quality_metrics.get("code_quality", 1.0) < 0.8:
            feedback_points.append("Content: Enhance code examples with better comments and explanations")

        if quality_metrics.get("engagement", 1.0) < 0.8:
            feedback_points.append("Content: Make the content more engaging with real-world applications")

    # Persona compliance feedback
    if hasattr(state.current_section, 'persona_compliance_score') and state.current_section.persona_compliance_score:
        if state.current_section.persona_compliance_score < 0.75:
            if hasattr(state.current_section, 'persona_violations') and state.current_section.persona_violations:
                for violation in state.current_section.persona_violations[:2]:  # Top 2 persona violations
                    feedback_points.append(f"Persona: {violation}")
            else:
                persona_name = getattr(state, 'persona', 'the selected')
                feedback_points.append(f"Persona: Better align content with {persona_name} persona voice and style")

                # Specific persona metrics feedback
                quality_metrics = getattr(state.current_section, "quality_metrics", {})
                if quality_metrics.get("voice_match", 1.0) < 0.7:
                    feedback_points.append(f"Persona: Adjust voice to match {persona_name} persona's distinctive style")

                if quality_metrics.get("tone_consistency", 1.0) < 0.7:
                    feedback_points.append(f"Persona: Maintain consistent {persona_name} tone throughout the section")

                if quality_metrics.get("audience_alignment", 1.0) < 0.7:
                    feedback_points.append(f"Persona: Better target {persona_name}'s intended audience")

    # Structural compliance feedback
    if hasattr(state.current_section, 'structural_compliance_score') and state.current_section.structural_compliance_score:
        if state.current_section.structural_compliance_score < 0.8:
            if hasattr(state.current_section, 'structural_violations') and state.current_section.structural_violations:
                for violation in state.current_section.structural_violations[:3]:  # Top 3 structural violations
                    feedback_points.append(f"Structure: {violation}")
            else:
                # Specific structural metrics feedback
                quality_metrics = getattr(state.current_section, "quality_metrics", {})

                if quality_metrics.get("paragraph_flow", 1.0) < 0.7:
                    feedback_points.append("Structure: Add 2-3 substantial paragraphs before introducing headings")

                if quality_metrics.get("heading_hierarchy", 1.0) < 0.8:
                    feedback_points.append("Structure: Fix heading hierarchy - use only H2 and H3 levels")

                if quality_metrics.get("no_fragmentation", 1.0) < 0.7:
                    feedback_points.append("Structure: Avoid fragmenting content - combine related short sections")

                if quality_metrics.get("list_usage", 1.0) < 0.7:
                    feedback_points.append("Structure: Use bullet/numbered lists for groups of 3+ related items")

                if quality_metrics.get("length_compliance", 1.0) < 0.7:
                    target = state.section_length_targets.get(state.current_section.title, 400)
                    current = len(state.current_section.content.split())
                    if current < target * 0.8:
                        feedback_points.append(f"Structure: Expand content to reach target length (~{target} words, current: {current})")
                    elif current > target * 1.2:
                        feedback_points.append(f"Structure: Condense content to target length (~{target} words, current: {current})")

    # If no specific issues, provide general enhancement feedback
    if not feedback_points:
        feedback_points = ["Consider adding more examples or deeper technical explanations to enhance the content"]

    # Format feedback with categories
    feedback = "Comprehensive feedback:\n• " + "\n• ".join(feedback_points)
    logger.debug(f"Generated comprehensive feedback with {len(feedback_points)} points")

    # Add feedback to the section
    state.current_section.feedback.append(SectionFeedback(
        content=feedback,
        source="auto",
        timestamp=datetime.now().isoformat(),
        addressed=False
    ))
    logger.debug(f"Added comprehensive feedback to section '{state.current_section.title}'")
    
    return state

@track_node_costs("feedback_inc", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def feedback_incorporator(state: BlogDraftState) -> BlogDraftState:
    """Incorporates feedback into the section content while maintaining original document structure."""
    logging.info("Executing node: feedback_incorporator")
    logger.debug(f"Feedback incorporator - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    if state.current_section is None:
        logging.warning("No current section to incorporate feedback.")
        logger.debug("No current section to incorporate feedback.")
        return state
    
    # Get the most recent feedback that hasn't been addressed
    unaddressed_feedback = [f for f in state.current_section.feedback if not f.addressed]
    if not unaddressed_feedback:
        logging.info("No unaddressed feedback to incorporate.")
        logger.debug("No unaddressed feedback to incorporate.")
        return state
    
    feedback = unaddressed_feedback[-1].content
    logger.debug(f"Found unaddressed feedback: {feedback[:50]}...")
    
    section_title = state.current_section.title
    section_index = state.current_section_index  # Use current index directly (0-based)
    learning_goals = state.outline.sections[section_index].learning_goals
    existing_content = state.current_section.content
    relevant_content = state.content_mapping.get(section_title, [])
    
    # Extract section headers from markdown metadata
    section_headers = []
    if (state.markdown_content and 
        hasattr(state.markdown_content, 'metadata') and 
        state.markdown_content.metadata and 
        'section_headers' in state.markdown_content.metadata):
        
        # section_headers = state.markdown_content.metadata['section_headers']
        
        section_headers = json.loads(state.markdown_content.metadata['section_headers'])
    
    # Find relevant headers for this section
    relevant_headers = []
    if section_headers:
        # Simple semantic matching for headers
        for header in section_headers:
            header_text = header.get('text', '').lower()
            section_text = section_title.lower()
            
            # Check for text overlap or containment
            if (header_text in section_text or 
                section_text in header_text or 
                any(goal.lower() in header_text for goal in learning_goals)):
                
                relevant_headers.append(header)
    
    # Format headers for the prompt
    original_structure = ""
    if relevant_headers:
        original_structure = "Original document structure:\n"
        # Sort by position or level
        sorted_headers = sorted(relevant_headers, key=lambda h: h.get('position', h.get('level', 1)))
        for header in sorted_headers:
            level = header.get('level', 1)
            text = header.get('text', '')
            indent = "  " * (level - 1)
            original_structure += f"{indent}{'#' * level} {text}\n"
    
    # Extract structural context from content references
    structural_insights = ""
    if relevant_content:
        # Find references with structural context
        structured_refs = [ref for ref in relevant_content if ref.structural_context]
        if structured_refs:
            structural_insights = "Structural insights from content analysis:\n"
            for ref in structured_refs[:3]:  # Limit to top 3
                if ref.structural_context:
                    structural_insights += f"- Content related to: {list(ref.structural_context.keys())}\n"
                    for header, context in ref.structural_context.items():
                        if context.get('parent'):
                            structural_insights += f"  - Parent topic: {context.get('parent')}\n"
                        if context.get('children'):
                            structural_insights += f"  - Related subtopics: {', '.join(context.get('children')[:3])}\n"
    
    # Check if feedback is about structural consistency
    structural_feedback = "structural" in feedback.lower() or "structure" in feedback.lower() or "organization" in feedback.lower()
    
    # Get current section constraints from outline
    section = state.outline.sections[section_index]
    
    # Prepare input variables for the prompt
    input_variables = {
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "existing_content": existing_content,
        "feedback": feedback,
        "original_structure": original_structure if structural_feedback else "",
        "structural_insights": structural_insights if structural_feedback else "",
        "current_section_data": json.dumps(section.model_dump())  # Pass section constraints including include_code
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["feedback_incorporation"]["prompt"].format(**input_variables)
    
    try:
        llm_response_str = await state.model.ainvoke(prompt)
        llm_response_str = llm_response_str if isinstance(llm_response_str, str) else llm_response_str.content
        
        logging.info(f"\n\nRaw LLM feedback incorporation response for {section_title}:\n{llm_response_str}\n\n")
        
        processed_content = llm_response_str # Default to the full response

        # Attempt to find and parse a JSON block if the LLM unexpectedly returns one
        # (though this node's prompt asks for direct Markdown)
        json_match = re.search(r'\{.*\}', llm_response_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                # Try to parse it as if it's a DraftSection or similar structure
                # We don't have a specific parser for this node, so we'll try a generic parse
                parsed_json = json.loads(json_str)
                if isinstance(parsed_json, dict) and "content" in parsed_json and isinstance(parsed_json["content"], str):
                    processed_content = parsed_json["content"]
                    logging.info(f"Extracted 'content' field from unexpected JSON in feedback_incorporator response.")
                else:
                    logging.warning("Found JSON in feedback_incorporator response, but it did not match expected structure (e.g., missing 'content' field). Using full response minus preamble if any.")
                    # Try to strip preamble if JSON was found but not usable
                    if llm_response_str.strip().startswith("{"): # If it starts with JSON
                        processed_content = json_str # Use the extracted JSON part
                    else: # It has preamble before JSON
                         # Heuristic: if there's text before the JSON, try to remove it.
                         # This is a bit risky and might need refinement.
                         lines = llm_response_str.splitlines()
                         json_start_line = -1
                         for i, line in enumerate(lines):
                             if line.strip().startswith("{"):
                                 json_start_line = i
                                 break
                         if json_start_line != -1: # Preamble detected
                             logging.info("Stripping preamble before JSON object in feedback_incorporator.")
                             processed_content = "\n".join(lines[json_start_line:])
                         # else: use llm_response_str as is (already default for processed_content)

            except json.JSONDecodeError:
                logging.warning(f"Could not parse JSON found in feedback_incorporator response. Using full response. JSON part: {json_str}")
        
        # Store the original content as a version
        state.current_section.versions.append(SectionVersion(
            content=state.current_section.content, # Old content
            version_number=state.current_section.current_version,
            timestamp=datetime.now().isoformat(),
            changes=f"Feedback incorporation: {feedback[:50]}..."
        ))
        
        # Validate and enforce constraints
        validated_content = validate_and_enforce_constraints(
            processed_content, 
            section.include_code, 
            section_title
        )
        
        # Update the section content and version
        state.current_section.content = validated_content
        state.current_section.current_version += 1
        
        # Mark feedback as addressed
        for f in unaddressed_feedback:
            f.addressed = True
        
    except Exception as e:
        logging.error(f"Error incorporating feedback: {e}")
        state.errors.append(f"Feedback incorporation failed: {str(e)}")
    
    return state

@track_node_costs("finalizer", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def section_finalizer(state: BlogDraftState) -> BlogDraftState:
    """Finalizes the current section."""
    logging.info("Executing node: section_finalizer")
    logger.debug(f"Section finalizer - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    # Update generation stage
    state.generation_stage = "finalizing"
    
    if state.current_section is None:
        logging.warning("No current section to finalize.")
        logger.debug("No current section to finalize.")
        return state
    
    # Log the section content to ensure it's captured
    section_title = state.current_section.title
    section_content_preview = state.current_section.content[:200] + "..." if len(state.current_section.content) > 200 else state.current_section.content
    logger.debug(f"Finalizing section '{section_title}' with content preview: {section_content_preview}")
    logging.info(f"Finalizing section '{section_title}' with content length: {len(state.current_section.content)} characters")
    
    # Mark the section as finalized
    state.current_section.status = "approved"
    logger.debug(f"Section '{section_title}' marked as approved")
    
    # Ensure the section is properly stored in the sections list
    if state.current_section not in state.sections:
        logger.debug(f"Warning: Current section '{section_title}' not found in sections list. Adding it now.")
        state.sections.append(state.current_section)
    
    # Reset iteration count for next section
    state.iteration_count = 0
    logger.debug("Reset iteration count to 0 for next section")

    # NEW: Save section to SQL if sql_project_manager is available
    if hasattr(state, 'sql_project_manager') and state.sql_project_manager and hasattr(state, 'project_id') and state.project_id:
        try:
            # Extract quality metrics if available
            quality_metrics = state.current_section.quality_metrics or {}
            word_count = len(state.current_section.content.split())

            # Extract actual costs from CostAggregator for this section
            section_cost = 0.0
            section_input_tokens = 0
            section_output_tokens = 0

            if hasattr(state, 'cost_aggregator') and state.cost_aggregator:
                section_key = f"section_{state.current_section_index}"
                section_costs = state.cost_aggregator.costs_by_section.get(section_key, {})
                section_cost = section_costs.get("total_cost", 0.0)
                section_tokens = section_costs.get("total_tokens", 0)

                # Get input/output token breakdown from call history for this section
                for call in state.cost_aggregator.call_history:
                    if call.get("section_index") == state.current_section_index:
                        section_input_tokens += call.get("input_tokens", 0)
                        section_output_tokens += call.get("output_tokens", 0)

            section_data = {
                "section_index": state.current_section_index,
                "title": state.current_section.title,
                "content": state.current_section.content,
                "status": SectionStatus.COMPLETED.value,
                "quality_score": quality_metrics.get("overall_score", 0.0),
                "word_count": word_count,
                "cost_delta": section_cost,
                "input_tokens": section_input_tokens,
                "output_tokens": section_output_tokens,
                "outline_hash": getattr(state, 'outline_hash', None)
            }

            # Save this single section (we'll batch save all sections at the end via save_sections)
            await state.sql_project_manager.save_sections(
                project_id=state.project_id,
                sections=[section_data]
            )
            logging.info(f"Saved section {state.current_section_index} to SQL for project {state.project_id}")
        except Exception as e:
            logging.error(f"Failed to save section to SQL: {e}")
            # Don't fail the workflow for SQL errors

    # Increment section index only after finalization is complete
    state.current_section_index += 1
    logger.debug(f"Advanced to section index {state.current_section_index}")
    logging.info(f"Section index advanced to {state.current_section_index} after finalizing '{section_title}'")

    return state

@track_node_costs("transition_gen", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def transition_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates transitions between sections."""
    logging.info("Executing node: transition_generator")
    logger.debug(f"Transition generator - Current section index: {state.current_section_index}, Total sections: {len(state.outline.sections)}")
    
    # If we've just finalized a section and there's another section coming up
    if (state.current_section_index < len(state.outline.sections) and 
        state.current_section_index > 0 and 
        len(state.sections) > 0):
        
        current_section = state.sections[-1]
        next_section_title = state.outline.sections[state.current_section_index].title
        
        logger.debug(f"Transition generator - Moving from '{current_section.title}' to '{next_section_title}'")
        logging.info(f"Generating transition from '{current_section.title}' to '{next_section_title}'")
        
        # Get the last 200 characters of the current section
        current_section_ending = current_section.content[-200:] if len(state.current_section.content) > 200 else current_section.content
        
        # Initialize persona service
        persona_service = PersonaService()
        # Get persona from state, with fallback to neuraforge
        persona_name = getattr(state, 'persona', 'neuraforge')
        persona_instructions = persona_service.get_persona_prompt(persona_name)
        logger.info(f"Using persona: {persona_name} for transition generation")
        
        # Prepare input variables for the prompt
        input_variables = {
            "persona_instructions": persona_instructions,
            "current_section_title": current_section.title,
            "current_section_ending": current_section_ending,
            "next_section_title": next_section_title,
            "blog_title": getattr(state.outline, 'title', 'Untitled Blog'),
            "current_section_index": state.current_section_index,
            "next_section_index": state.current_section_index + 1,
            "total_sections": len(state.outline.sections)
        }
        
        # Format prompt and get LLM response
        prompt = PROMPT_CONFIGS["section_transition"]["prompt"].format(**input_variables)
        
        try:
            response = await state.model.ainvoke(prompt)
            
            response = response if isinstance(response, str) else response.content
            
            # Log the response content
            logging.info(f"\n\nTransition generation response from {current_section.title} to {next_section_title}:\n{response}\n\n")
            
            # Store the transition
            state.transitions[f"{current_section.title}_to_{next_section_title}"] = response
            
            logger.debug(f"Successfully generated transition from '{current_section.title}' to '{next_section_title}'")
            logger.debug(f"Next section to generate: '{next_section_title}'")
            
        except Exception as e:
            logging.error(f"Error generating transition: {e}")
            state.errors.append(f"Transition generation failed: {str(e)}")
            logger.debug(f"Error generating transition: {e}")
    else:
        if state.current_section_index >= len(state.outline.sections):
            logger.debug("Transition generator - All sections have been generated, moving to blog compilation")
        else:
            logger.debug(f"Transition generator - No transition needed (first section or no sections yet)")
    
    return state

def format_section_with_images(section: DraftSection) -> str:
    """Format a section with its content and image placeholders."""
    content_parts = [f"## {section.title}"]
    
    # If there are image placeholders, integrate them with the content
    if section.image_placeholders:
        section_content = section.content
        
        for placeholder in section.image_placeholders:
            # Create formatted image placeholder
            image_markdown = f"""
[IMAGE_PLACEHOLDER: {placeholder.type} - {placeholder.description}]
Alt text: {placeholder.alt_text}
Placement: {placeholder.placement}
Purpose: {placeholder.purpose}
"""
            
            # Insert image placeholder based on placement strategy
            if placeholder.placement == "section_start":
                # Add right after the section title
                content_parts.append(image_markdown)
                content_parts.append(section_content)
            elif placeholder.placement == "section_end":
                # Add at the end of the section
                content_parts.append(section_content)
                content_parts.append(image_markdown)
            elif placeholder.placement == "after_concept":
                # Try to insert after the first paragraph (simple heuristic)
                paragraphs = section_content.split('\n\n')
                if len(paragraphs) > 1:
                    content_parts.append(paragraphs[0])
                    content_parts.append(image_markdown)
                    content_parts.append('\n\n'.join(paragraphs[1:]))
                else:
                    content_parts.append(section_content)
                    content_parts.append(image_markdown)
            else:
                # Default: add after content
                content_parts.append(section_content)
                content_parts.append(image_markdown)
    else:
        # No image placeholders, just add the content
        content_parts.append(section.content)
    
    return '\n\n'.join(content_parts)

@track_node_costs("compiler", agent_name="BlogDraftGeneratorAgent", stage="draft_generation")
async def blog_compiler(state: BlogDraftState) -> BlogDraftState:
    """Compiles the final blog post while maintaining original document structure."""
    logging.info("Executing node: blog_compiler")
    
    # Update generation stage
    state.generation_stage = "compiling"
    
    # Get blog metadata
    blog_title = state.outline.title
    difficulty_level = state.outline.difficulty_level
    prerequisites = state.outline.prerequisites
    
    # Extract section headers from markdown metadata
    section_headers = []
    if (state.markdown_content and 
        hasattr(state.markdown_content, 'metadata') and 
        state.markdown_content.metadata and 
        'section_headers' in state.markdown_content.metadata):
        
        # section_headers = state.markdown_content.metadata['section_headers']
        section_headers = json.loads(state.markdown_content.metadata['section_headers'])
    
    # Format original document structure for the prompt
    original_structure = ""
    if section_headers:
        original_structure = "Original document structure:\n"
        # Sort by position or level
        sorted_headers = sorted(section_headers, key=lambda h: h.get('position', h.get('level', 1)))
        for header in sorted_headers:
            level = header.get('level', 1)
            text = header.get('text', '')
            indent = "  " * (level - 1)
            original_structure += f"{indent}{'#' * level} {text}\n"
    
    # Get sections content with image placeholders
    sections_content = "\n\n".join([
        format_section_with_images(section)
        for section in state.sections
    ])
    
    # Get transitions
    transitions = "\n\n".join([
        f"{key}:\n{value}"
        for key, value in state.transitions.items()
    ])
    
    # Initialize persona service
    persona_service = PersonaService()
    # Get persona from state, with fallback to neuraforge
    persona_name = getattr(state, 'persona', 'neuraforge')
    persona_instructions = persona_service.get_persona_prompt(persona_name)
    logger.info(f"Using persona: {persona_name} for blog compilation")
    
    # Prepare input variables for the prompt
    input_variables = {
        "persona_instructions": persona_instructions,
        "blog_title": blog_title,
        "difficulty_level": difficulty_level,
        "prerequisites": prerequisites,
        "sections_content": sections_content,
        "transitions": transitions,
        "original_structure": original_structure
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["blog_compilation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        response = response if isinstance(response, str) else response.content
        
        # Log the response content
        logging.info(f"\n\nBlog compilation response:\n{response}\n\n")
        
        # Store the final blog post
        state.final_blog_post = response

        # Update generation stage
        state.generation_stage = "completed"

        # NEW: Save DRAFT_COMPLETED milestone to SQL
        if hasattr(state, 'sql_project_manager') and state.sql_project_manager and hasattr(state, 'project_id') and state.project_id:
            try:
                # Calculate total word count and quality metrics
                total_word_count = sum(len(section.content.split()) for section in state.sections)
                section_quality_scores = [
                    {
                        "section_index": idx,
                        "title": section.title,
                        "quality_score": section.quality_metrics.get("overall_score", 0.0) if section.quality_metrics else 0.0,
                        "word_count": len(section.content.split())
                    }
                    for idx, section in enumerate(state.sections)
                ]

                milestone_data = {
                    "compiled_blog": response,
                    "total_sections": len(state.sections),
                    "total_word_count": total_word_count,
                    "section_quality_scores": section_quality_scores
                }

                await state.sql_project_manager.save_milestone(
                    project_id=state.project_id,
                    milestone_type=MilestoneType.DRAFT_COMPLETED,
                    data=milestone_data
                )
                logging.info(f"Saved DRAFT_COMPLETED milestone for project {state.project_id}")
            except Exception as e:
                logging.error(f"Failed to save draft completion milestone: {e}")
                # Don't fail the workflow for SQL errors

    except Exception as e:
        logging.error(f"Error compiling blog: {e}")
        state.errors.append(f"Blog compilation failed: {str(e)}")

    return state
