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
        state.errors.append(f"Validation error: {str(e)}")
    return state

async def parse_content(state: ContentParsingState) -> ContentParsingState:
    """Parses the file content."""
    if not state.validation_result or not all(state.validation_result.values()):
        return state
        
    try:
        parser = ParserFactory.get_parser(state.file_path)
        state.parsed_content = parser.parse()
    except Exception as e:
        state.errors.append(f"Parsing error: {str(e)}")
    return state

def _chunk_content(sections: List[Dict]) -> List[str]:
    """Simple content chunking strategy."""
    chunks = []
    current_chunk = []
    current_size = 0
    max_chunk_size = 1000  # characters
    
    for section in sections:
        content = section.get("content", "")
        if not content:
            continue
            
        # If content is too large, split it
        if len(content) > max_chunk_size:
            # Add any existing content as a chunk
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_size = 0
            
            # Split large content into smaller chunks
            words = content.split()
            temp_chunk = []
            temp_size = 0
            
            for word in words:
                if temp_size + len(word) + 1 > max_chunk_size:
                    chunks.append(" ".join(temp_chunk))
                    temp_chunk = [word]
                    temp_size = len(word)
                else:
                    temp_chunk.append(word)
                    temp_size += len(word) + 1
            
            if temp_chunk:
                chunks.append(" ".join(temp_chunk))
        else:
            # If adding this section would exceed chunk size, create new chunk
            if current_size + len(content) > max_chunk_size:
                chunks.append("\n".join(current_chunk))
                current_chunk = [content]
                current_size = len(content)
            else:
                current_chunk.append(content)
                current_size += len(content)
    
    # Add any remaining content
    if current_chunk:
        chunks.append("\n".join(current_chunk))
    
    return chunks

async def chunk_content(state: ContentParsingState) -> ContentParsingState:
    """Chunks the parsed content."""
    if not state.parsed_content:
        return state
        
    try:
        state.content_chunks = _chunk_content(state.parsed_content.sections)
    except Exception as e:
        state.errors.append(f"Chunking error: {str(e)}")
    return state

async def prepare_metadata(state: ContentParsingState) -> ContentParsingState:
    """Prepares metadata for storage."""
    if not state.parsed_content:
        return state
        
    try:
        path = Path(state.file_path)
        state.metadata = {
            "file_name": path.name,
            "file_path": str(path),
            "project_name": state.project_name,
            "content_type": state.parsed_content.content_type,
            "processed_at": datetime.now().isoformat(),
            "file_type": path.suffix.lower()
        }
    except Exception as e:
        state.errors.append(f"Metadata error: {str(e)}")
    return state

async def store_content(state: ContentParsingState) -> ContentParsingState:
    """Stores the processed content."""
    if not (state.content_chunks and state.metadata):
        return state
        
    try:
        vector_store = VectorStoreService()
        content_hash = vector_store.compute_content_hash(
            "".join(state.content_chunks), 
            ""
        )
        vector_store.store_content_chunks(
            chunks=state.content_chunks,
            metadata=[state.metadata] * len(state.content_chunks),
            content_hash=content_hash
        )
        state.content_hash = content_hash
    except Exception as e:
        state.errors.append(f"Storage error: {str(e)}")
    return state
