import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity # Added for semantic similarity
from root.backend.agents.blog_draft_generator.state import BlogDraftState, DraftSection, ContentReference, CodeExample, SectionVersion, SectionFeedback
from root.backend.agents.blog_draft_generator.prompts import PROMPT_CONFIGS
from root.backend.agents.blog_draft_generator.utils import (
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
from root.backend.services.vector_store_service import VectorStoreService

logging.basicConfig(level=logging.INFO)

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


async def section_generator(state: BlogDraftState) -> BlogDraftState:
    """Generates content for current section using retrieved HyDE context."""
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
    
    print(f"Section generator - Generating content for '{section_title}' using HyDE context")

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

    # Get previous section content for context if available
    previous_context = ""
    if state.current_section_index > 0 and state.sections:
        prev_section = state.sections[-1]
        previous_context = f"""
        Previous Section: {prev_section.title}
        Content Summary: {prev_section.content[:300]}...
        """
    
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

    # Prepare input variables for the prompt, using formatted_hyde_context
    input_variables = {
        "format_instructions": PROMPT_CONFIGS["section_generation"]["parser"].get_format_instructions() if PROMPT_CONFIGS["section_generation"]["parser"] else "",
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "formatted_content": formatted_hyde_context, # Use HyDE context here
        "previous_context": previous_context,
        # Keep original_structure and structural_insights for now, though their relevance might decrease
        "original_structure": original_structure,
        "structural_insights": structural_insights
    }

    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["section_generation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        # Handle potential string response vs. object response
        section_content = response if isinstance(response, str) else response.content
        
        # Log the response content
        logging.info(f"\n\nSection generation response for {section_title}:\n{section_content}\n\n")
        
        # Create a new draft section
        draft_section = DraftSection(
            title=section_title,
            content=section_content,
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
    """Enhances section content while maintaining original document structure."""
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
    
    # Prepare input variables for the prompt
    input_variables = {
        "format_instructions": PROMPT_CONFIGS["content_enhancement"]["parser"].get_format_instructions() if PROMPT_CONFIGS["content_enhancement"]["parser"] else "",
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "existing_content": existing_content,
        "formatted_content": formatted_content,
        "original_structure": original_structure,
        "structural_insights": structural_insights
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["content_enhancement"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        response = response if isinstance(response, str) else response.content
        
        # Log the response content
        logging.info(f"\n\nContent enhancement response for {section_title}:\n{response}\n\n")
        
        # Store the original content as a version
        state.current_section.versions.append(SectionVersion(
            content=state.current_section.content,
            version_number=state.current_section.current_version,
            timestamp=datetime.now().isoformat(),
            changes="Initial enhancement"
        ))
        
        # Update the section content
        state.current_section.content = response
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
        
        response = response if isinstance(response, str) else response.content
        
        # Log the response content
        logging.info(f"\n\nQuality validation response for {section_title}:\n{response}\n\n")
        
        # Parse the response
        parsed_result = parse_json_safely(response, {})
        logging.info(f"Parsed quality validation result: {parsed_result}")

        # --- Robust Quality Metric Handling ---
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
                    logging.warning(f"Metric '{metric}' missing or invalid type in quality validation response for '{section_title}'. Response: {response}")
                    # Assign a default low score if missing/invalid to trigger feedback
                    quality_metrics[metric] = 0.0
                    # We might consider parsing_successful = False here too, depending on strictness
                else:
                    quality_metrics[metric] = float(parsed_result[metric])

        # If parsing failed completely, assign all defaults
        if not parsing_successful:
             quality_metrics = {metric: 0.0 for metric in required_metrics}
             logging.info(f"Assigned default low scores for '{section_title}' due to parsing failure.")

        # Store quality metrics
        state.current_section.quality_metrics = quality_metrics
        # --- End of Robust Handling ---

        # Calculate overall score if it wasn't correctly parsed or provided (as a fallback)
        # Note: The robust handling above already assigns 0.0 if 'overall_score' is missing/invalid
        if "overall_score" not in quality_metrics or quality_metrics["overall_score"] == 0.0 and parsing_successful and any(quality_metrics[m] > 0.0 for m in quality_metrics if m != "overall_score"):
            logging.warning(f"Recalculating overall_score for '{section_title}' as it was missing or potentially invalid.")
            metrics = quality_metrics
            valid_scores = [metrics[m] for m in required_metrics if m != "overall_score" and m in metrics]
            overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
            state.current_section.quality_metrics["overall_score"] = overall
            print(f"Recalculated overall score: {overall}")

        # Determine if improvement is needed based on overall score
        # Use the potentially updated overall_score
        overall_score = state.current_section.quality_metrics.get("overall_score", 0.0)
        # Lowered threshold slightly as semantic matching might be stricter
        quality_threshold = state.quality_threshold # Use threshold from state
        improvement_needed = overall_score < quality_threshold
        print(f"Overall score: {overall_score:.2f}, Quality Threshold: {quality_threshold}, Improvement needed: {improvement_needed}")

        # --- The following block seems duplicated/incorrectly placed after the previous edit ---
        # --- Removing it to fix syntax errors ---
        # "completeness": result.get("completeness", 0.0),
        # "technical_accuracy": result.get("technical_accuracy", 0.0),
        # "clarity": result.get("clarity", 0.0),
        # "code_quality": result.get("code_quality", 0.0),
        # "engagement": result.get("engagement", 0.0),
        # "structural_consistency": result.get("structural_consistency", 0.0),
        # "overall_score": result.get("overall_score", 0.0)
        # }
        
        # Calculate overall score if not provided (This logic is already handled above)
        if "overall_score" not in state.current_section.quality_metrics:
            metrics = state.current_section.quality_metrics
            overall = sum([
                metrics.get("completeness", 0.0),
                metrics.get("technical_accuracy", 0.0),
                metrics.get("clarity", 0.0),
                metrics.get("code_quality", 0.0),
                metrics.get("engagement", 0.0),
                metrics.get("structural_consistency", 0.0)
            ]) / 6.0
            # state.current_section.quality_metrics["overall_score"] = overall # Already handled
            # print(f"Calculated overall score: {overall}") # Already handled

        # Determine if improvement is needed based on overall score (This logic is already handled above)
        # overall_score = state.current_section.quality_metrics.get("overall_score", 0.0) # Already handled
        # improvement_needed = overall_score < 0.85  # Set a threshold for quality # Already handled
        # print(f"Overall score: {overall_score}, Improvement needed: {improvement_needed}") # Already handled

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
    
    if quality_metrics.get("structural_consistency", 1.0) < 0.8:
        feedback_points.append("Better align the content with the original document's structure and organization.")
    
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
    """Incorporates feedback into the section content while maintaining original document structure."""
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
    
    # Prepare input variables for the prompt
    input_variables = {
        "section_title": section_title,
        "learning_goals": ", ".join(learning_goals),
        "existing_content": existing_content,
        "feedback": feedback,
        "original_structure": original_structure if structural_feedback else "",
        "structural_insights": structural_insights if structural_feedback else ""
    }
    
    # Format prompt and get LLM response
    prompt = PROMPT_CONFIGS["feedback_incorporation"]["prompt"].format(**input_variables)
    
    try:
        response = await state.model.ainvoke(prompt)
        
        response = response if isinstance(response, str) else response.content
        
        # Log the response content
        logging.info(f"\n\nFeedback incorporation response for {section_title}:\n{response}\n\n")
        
        # Store the original content as a version
        state.current_section.versions.append(SectionVersion(
            content=state.current_section.content,
            version_number=state.current_section.current_version,
            timestamp=datetime.now().isoformat(),
            changes=f"Feedback incorporation: {feedback[:50]}..."
        ))
        
        # Update the section content and version
        state.current_section.content = response
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
            
            response = response if isinstance(response, str) else response.content
            
            # Log the response content
            logging.info(f"\n\nTransition generation response from {current_section.title} to {next_section_title}:\n{response}\n\n")
            
            # Store the transition
            state.transitions[f"{current_section.title}_to_{next_section_title}"] = response
            
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
        
    except Exception as e:
        logging.error(f"Error compiling blog: {e}")
        state.errors.append(f"Blog compilation failed: {str(e)}")
    
    return state
