"""
Processing nodes for content parsing graph.
"""
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict

from root.backend.parsers import ParserFactory
from root.backend.services.vector_store_service import VectorStoreService
from .state import ContentParsingState

logging.basicConfig(level=logging.INFO)

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

async def parse_content(state: ContentParsingState) -> ContentParsingState:
    """Parses the file content."""
    if not state.validation_result or not all(state.validation_result.values()):
        logging.warning(f"No Validated content to parse")
        return state
        
    try:
        parser = ParserFactory.get_parser(state.file_path)
        state.parsed_content = parser.parse()
    except Exception as e:
        state.errors.append(f"Parsing error: {str(e)}")
    return state

def _chunk_content(sections: List[Dict]) -> List[Dict]:
    """Enhanced content chunking strategy that preserves section context."""
    chunks = []
    current_chunk = []
    current_size = 0
    max_chunk_size = 1000  # characters
    current_section_info = None
    
    for section in sections:
        content = section.get("content", "")
        if not content:
            continue
            
        # Capture section header information if available
        section_info = None
        if "header_text" in section and "header_level" in section:
            section_info = {
                "header_text": section["header_text"],
                "header_level": section["header_level"]
            }
            current_section_info = section_info
            
        # If content is too large, split it
        if len(content) > max_chunk_size:
            # Add any existing content as a chunk
            if current_chunk:
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "section_info": current_section_info
                })
                current_chunk = []
                current_size = 0
            
            # Split large content into smaller chunks
            words = content.split()
            temp_chunk = []
            temp_size = 0
            
            for word in words:
                if temp_size + len(word) + 1 > max_chunk_size:
                    chunks.append({
                        "content": " ".join(temp_chunk),
                        "section_info": current_section_info
                    })
                    temp_chunk = [word]
                    temp_size = len(word)
                else:
                    temp_chunk.append(word)
                    temp_size += len(word) + 1
            
            if temp_chunk:
                chunks.append({
                    "content": " ".join(temp_chunk),
                    "section_info": current_section_info
                })
        else:
            # If adding this section would exceed chunk size, create new chunk
            if current_size + len(content) > max_chunk_size:
                chunks.append({
                    "content": "\n".join(current_chunk),
                    "section_info": current_section_info
                })
                current_chunk = [content]
                current_size = len(content)
            else:
                current_chunk.append(content)
                current_size += len(content)
    
    # Add any remaining content
    if current_chunk:
        chunks.append({
            "content": "\n".join(current_chunk),
            "section_info": current_section_info
        })
    
    return chunks

async def chunk_content(state: ContentParsingState) -> ContentParsingState:
    """Chunks the parsed content."""
    if not state.parsed_content:
        logging.warning("No parsed content available for chunking")
        state.errors.append("No parsed content available for chunking")
        return state
        
    try:
        # Create sections from main_content and code_segments
        sections = []
        
        # Add main content as a section, preserving section headers if present
        if state.parsed_content.main_content:
            # If we have section headers in the metadata, use them to create separate sections
            if (hasattr(state.parsed_content, 'metadata') and 
                'section_headers' in state.parsed_content.metadata and
                state.parsed_content.metadata['section_headers']):
                
                import json
                section_headers = json.loads(state.parsed_content.metadata['section_headers'])
                
                # Split main content by section headers
                # For simplicity, just use the existing section handling for now
                section = {
                    "content": state.parsed_content.main_content,
                    "type": "markdown"
                }
                sections.append(section)
            else:
                sections.append({
                    "content": state.parsed_content.main_content,
                    "type": "markdown"
                })
            
        # Add code segments as sections
        if hasattr(state.parsed_content, 'code_segments') and state.parsed_content.code_segments:
            for code in state.parsed_content.code_segments:
                sections.append({
                    "content": code,
                    "type": "code"
                })
            
        # Get chunks with section info
        chunk_results = _chunk_content(sections)
        
        # Extract content chunks and prepare per-chunk metadata
        state.content_chunks = []
        state.chunk_metadata = []
        
        logging.info(f"Number of chunk results: {len(chunk_results)}")
        
        for chunk_result in chunk_results:
            state.content_chunks.append(chunk_result["content"])
            
            # Prepare per-chunk metadata to include section info
            chunk_metadata = {}
            if "section_info" in chunk_result and chunk_result["section_info"]:
                chunk_metadata["section_info"] = chunk_result["section_info"]
            state.chunk_metadata.append(chunk_metadata)
            
        logging.info(f"Chunking complete: {len(state.content_chunks)} chunks created")
    except Exception as e:
        error_msg = f"Chunking error: {str(e)}"
        logging.error(error_msg)
        state.errors.append(error_msg)
    return state

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
