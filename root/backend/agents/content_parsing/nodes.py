"""
Processing nodes for content parsing graph.
"""
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict

# LangChain imports for text splitting
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    PythonCodeTextSplitter,
    TextSplitter
)

from backend.parsers import ParserFactory, ContentStructure
from backend.services.vector_store_service import VectorStoreService
from backend.agents.cost_tracking_decorator import track_node_costs
from .state import ContentParsingState

logging.basicConfig(level=logging.INFO)

@track_node_costs("validate_file", agent_name="ContentParsingAgent", stage="content_parsing")
async def validate_file(state: ContentParsingState) -> ContentParsingState:
    """Validates the input file."""
    try:
        path = Path(state.file_path)
        validation = {
            "exists": path.exists(),
            "supported_type": path.suffix.lower() in ParserFactory.supported_extensions(),
            "not_empty": path.stat().st_size > 0
        }
        state.validation_result = validation
                
        if not all(validation.values()):
            state.errors.append(f"Validation failed: {validation}")
    except Exception as e:
        logging.error(f"Validation error: {str(e)}")
        state.errors.append(f"Validation error: {str(e)}")
    return state

@track_node_costs("parse_content", agent_name="ContentParsingAgent", stage="content_parsing")
async def parse_content(state: ContentParsingState) -> ContentParsingState:
    """Parses the file content."""
    if not state.validation_result or not all(state.validation_result.values()):
        logging.warning(f"No Validated content to parse")
        return state
        
    try:
        parser = ParserFactory.get_parser(state.file_path)
        state.parsed_content = parser.parse()
    except Exception as e:
        error_msg = f"Parsing error: {str(e)}"
        state.errors.append(error_msg)
        logging.exception(f"Exception during parsing of {state.file_path}") # Log full traceback
        # Ensure parsed_content is set to an empty structure on error
        state.parsed_content = ContentStructure(main_content="", code_segments=[], content_type="unknown", metadata={"error": error_msg})
    
    # Check for empty content *after* the try-except block
    if not state.parsed_content or not state.parsed_content.main_content:
         # Check if there was an error stored in metadata by the parser itself
         parse_error = state.parsed_content.metadata.get("error") if state.parsed_content else "Unknown parsing issue (parser returned None or empty content)"
         # Avoid adding duplicate errors if already caught by exception
         if f"Parsing failed or returned empty content: {parse_error}" not in state.errors and f"Parsing error: {parse_error}" not in state.errors:
              state.errors.append(f"Parsing failed or returned empty content: {parse_error}")
              logging.error(f"Parsing failed for {state.file_path}: {parse_error}")
         # Ensure state.parsed_content is a valid (even if empty) ContentStructure object if it somehow became None
         if not state.parsed_content:
             state.parsed_content = ContentStructure(main_content="", code_segments=[], content_type="unknown", metadata={"error": parse_error})

    return state
# Removed the old _chunk_content helper function as it's replaced by LangChain splitters

@track_node_costs("chunk_content", agent_name="ContentParsingAgent", stage="content_parsing")
async def chunk_content(state: ContentParsingState) -> ContentParsingState:
    """Chunks the parsed content using appropriate LangChain text splitters."""
    if not state.parsed_content:
        logging.warning("No parsed content available for chunking")
        state.errors.append("No parsed content available for chunking")
        return state

    try:
        # Default chunking parameters (can be made configurable later)
        chunk_size = 1000
        chunk_overlap = 200

        # Initialize splitters
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        python_splitter = PythonCodeTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        # Markdown splitter requires headers - adjust if parser provides them
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False # Keep headers in the content
        )

        all_docs = [] # Will store LangChain Document objects

        # Process main content (likely markdown or text)
        if state.parsed_content.main_content:
            content_type = state.parsed_content.content_type
            main_content = state.parsed_content.main_content

            splitter: TextSplitter # Type hint for clarity

            if content_type == 'markdown':
                # Try Markdown splitter first, fallback to recursive
                try:
                    # MarkdownHeaderTextSplitter expects metadata to be merged later
                    md_docs = markdown_splitter.split_text(main_content)
                    # Add file-level metadata to each doc later
                    all_docs.extend(md_docs)
                    logging.info(f"Used MarkdownHeaderTextSplitter for main content.")
                except Exception as md_err:
                    logging.warning(f"MarkdownHeaderTextSplitter failed ({md_err}), falling back to RecursiveCharacterTextSplitter.")
                    docs = recursive_splitter.create_documents([main_content])
                    all_docs.extend(docs)
            else: # Treat as plain text or other types
                logging.info(f"Using RecursiveCharacterTextSplitter for main content (type: {content_type}).")
                docs = recursive_splitter.create_documents([main_content])
                all_docs.extend(docs)

        # Process code segments
        if hasattr(state.parsed_content, 'code_segments') and state.parsed_content.code_segments:
            logging.info(f"Processing {len(state.parsed_content.code_segments)} code segments.")
            # Assume Python for now, could be enhanced based on file type
            # Combine segments before splitting to maintain context if possible,
            # or split individually if they represent distinct blocks.
            # For simplicity, splitting individually here.
            for code_segment in state.parsed_content.code_segments:
                 # Check if segment is not empty or just whitespace
                if code_segment and not code_segment.isspace():
                    try:
                        code_docs = python_splitter.create_documents([code_segment])
                        # Add metadata indicating this is a code chunk
                        for doc in code_docs:
                            doc.metadata["content_part"] = "code"
                        all_docs.extend(code_docs)
                    except Exception as py_err:
                        logging.warning(f"PythonCodeTextSplitter failed ({py_err}), falling back to RecursiveCharacterTextSplitter for code segment.")
                        # Fallback for code that might not parse perfectly
                        fallback_docs = recursive_splitter.create_documents([code_segment])
                        for doc in fallback_docs:
                            doc.metadata["content_part"] = "code_fallback"
                        all_docs.extend(fallback_docs)
                else:
                    logging.debug("Skipping empty or whitespace-only code segment.")


        # Extract page content and metadata from LangChain Documents
        state.content_chunks = [doc.page_content for doc in all_docs]
        # Start with metadata from the LangChain documents themselves
        state.chunk_metadata = [doc.metadata for doc in all_docs]

        logging.info(f"Chunking complete: {len(state.content_chunks)} chunks created using LangChain splitters.")

    except Exception as e:
        error_msg = f"Chunking error using LangChain splitters: {str(e)}"
        logging.exception(error_msg) # Log traceback for better debugging
        state.errors.append(error_msg)
    return state


@track_node_costs("prepare_metadata", agent_name="ContentParsingAgent", stage="content_parsing")
async def prepare_metadata(state: ContentParsingState) -> ContentParsingState:
    """Prepares metadata for storage."""
    if not state.parsed_content:
        return state
        
    try:
        path = Path(state.file_path)
        # Base metadata
        base_metadata = {
            "file_name": path.name,
            "file_path": str(path),
            "project_name": state.project_name,
            "content_type": state.parsed_content.content_type,
            "processed_at": datetime.now().isoformat(),
            "file_type": path.suffix.lower()
        }
        
        # Merge with content-specific metadata from the parser
        if hasattr(state.parsed_content, 'metadata') and state.parsed_content.metadata:
            base_metadata.update(state.parsed_content.metadata)
            
        state.metadata = base_metadata
    except Exception as e:
        state.errors.append(f"Metadata error: {str(e)}")
    return state

@track_node_costs("store_content", agent_name="ContentParsingAgent", stage="content_parsing")
async def store_content(state: ContentParsingState) -> ContentParsingState:
    """Stores the processed content."""
    # Replace print statements with proper logging
    logging.info(f"Content chunks available: {bool(state.content_chunks)}, Metadata available: {bool(state.metadata)}")
    
    if not state.content_chunks or not state.metadata:
        logging.warning("Missing content chunks or metadata, skipping storage")
        state.errors.append("Missing content chunks or metadata for storage")
        return state
        
    try:
        vector_store = VectorStoreService()
        
        # Log the content chunks for debugging
        logging.info(f"Number of content chunks: {len(state.content_chunks)}")
        
        # Generate content hash
        content_hash = vector_store.compute_content_hash(
            "".join(state.content_chunks), 
            ""
        )
        logging.info(f"Generated content hash: {content_hash}")
        
        # Create combined metadata for each chunk by merging base metadata with chunk-specific metadata
        combined_metadata = []
        for i, chunk in enumerate(state.content_chunks):
            chunk_metadata = state.metadata.copy()
            
            # Add chunk-specific metadata if available
            if hasattr(state, 'chunk_metadata') and state.chunk_metadata and i < len(state.chunk_metadata) and state.chunk_metadata[i] is not None:
                chunk_metadata.update(state.chunk_metadata[i])
                
            # Add content hash to metadata
            chunk_metadata["content_hash"] = content_hash
                
            combined_metadata.append(chunk_metadata)
        
        # Store content in vector store
        vector_store.store_content_chunks(
            chunks=state.content_chunks,
            metadata=combined_metadata,
            content_hash=content_hash
        )
        
        # Set content hash in state
        state.content_hash = content_hash
        logging.info(f"Successfully stored content with hash: {content_hash}")
    except Exception as e:
        error_msg = f"Storage error: {str(e)}"
        logging.error(error_msg)
        state.errors.append(error_msg)
        # Make sure to return state even on error
    
    # Explicitly log the state before returning
    logging.info(f"Final state content_hash: {getattr(state, 'content_hash', None)}")
    return state
