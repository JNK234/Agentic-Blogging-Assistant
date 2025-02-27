"""
Simplified content parsing agent that processes files and stores them in ChromaDB.
Handles markdown, python files, and Jupyter notebooks for blog content generation.
"""
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path
from datetime import datetime

from ..parsers import ParserFactory, ContentStructure
from ..services.vector_store_service import VectorStoreService
from root.backend.agents.base_agent import BaseGraphAgent
from root.backend.agents.content_parsing.state import ContentParsingState
from root.backend.agents.content_parsing.graph import create_parsing_graph

logging.basicConfig(level=logging.INFO)

class ContentParsingAgent(BaseGraphAgent):
    """Agent responsible for parsing content and storing it in vector store."""
    
    def __init__(self, llm=None):  # llm optional since this agent doesn't use it directly
        super().__init__(
            llm=llm,
            tools=[],
            state_class=ContentParsingState,
            verbose=True
        )
        self.vector_store = VectorStoreService()
        self._initialized = False
        
    async def initialize(self):
        """Public method to initialize the agent."""
        if hasattr(self, '_initialized') and self._initialized:
            logging.info("ContentParsingAgent already initialized")
            return
            
        # Initialize the graph
        self.graph = await create_parsing_graph(self.state_class)
        self._initialized = True
        logging.info("ContentParsingAgent initialized")
        
    def _validate_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Basic file validation."""
        try:
            path = Path(file_path)
            # Convert path to absolute path
            path = path.resolve()
            print(path)
            if not path.exists():
                return False, f"File not found: {file_path}"
            if path.suffix.lower() not in ParserFactory.supported_extensions():
                return False, f"Unsupported file type: {path.suffix}"
            if path.stat().st_size == 0:
                return False, "File is empty"
            return True, None
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    async def process_file_with_graph(self, file_path: str, project_name: Optional[str] = None) -> Optional[str]:
        """Process a single file using the graph-based approach."""
        try:
            # Check if file already exists in project
            path = Path(file_path)
            file_metadata = {
                "file_name": path.name,
                "file_path": str(path),
                "project_name": project_name,
                "file_type": path.suffix.lower()
            }
            
            existing = self.search_content(
                metadata_filter=file_metadata
            )
            if existing:
                logging.info(f"File already exists in project: {file_path}")
                return existing[0]["metadata"]["content_hash"]
                
            # Initialize state
            initial_state = self.state_class(
                file_path=file_path,
                project_name=project_name
            )
            
            # Execute graph
            final_state = await self.run_graph(initial_state)
            
            if final_state.errors:
                logging.error(f"Errors during processing: {final_state.errors}")
                return None
                
            return final_state.content_hash
            
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            return None
            
    def process_file(self, file_path: str, project_name: Optional[str] = None) -> Optional[str]:
        """Process a single file and store its content."""
        # For backward compatibility, we'll keep the synchronous method
        # but in the future, we should transition to using the async graph-based approach
        try:
            # Validate first
            is_valid, error_msg = self._validate_file(file_path)
            if not is_valid:
                logging.error(f"File validation failed: {error_msg}")
                return None

            # Create basic metadata
            path = Path(file_path)
            file_metadata = {
                "file_name": path.name,
                "file_path": str(path),
                "project_name": project_name,
                "file_type": path.suffix.lower()
            }
            
            # Check if file already exists in project
            existing = self.search_content(
                metadata_filter=file_metadata
            )
            if existing:
                logging.info(f"File already exists in project: {file_path}")
                return existing[0]["metadata"]["content_hash"]

            # If not found, proceed with parsing and storing
            parser = ParserFactory.get_parser(file_path)
            content = parser.parse()
            chunks = self._chunk_content(content.sections)
            
            # Add additional metadata
            metadata = {
                **file_metadata,
                "content_type": content.content_type,
                "processed_at": datetime.now().isoformat()
            }
            
            # Generate hash after confirming it's new content
            content_hash = self.vector_store.compute_content_hash("".join(chunks), "")
            
            # Store the content
            self.vector_store.store_content_chunks(
                chunks=chunks,
                metadata=[metadata] * len(chunks),
                content_hash=content_hash
            )
            
            logging.info(f"Successfully processed new file: {file_path}")
            return content_hash
            
        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            return None
    
    def _create_metadata(self, file_path: str, content_type: str, project_name: Optional[str] = None) -> Dict:
        """Create basic metadata for content."""
        path = Path(file_path)
        return {
            "file_name": path.name,
            "file_path": str(path),
            "content_type": content_type,
            "project_name": project_name,
            "processed_at": datetime.now().isoformat(),
            "file_type": path.suffix.lower()
        }

    def _chunk_content(self, sections: List[Dict]) -> List[str]:
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
        
    def search_content(self, metadata_filter: Dict, query: Optional[str] = None) -> List[Dict]:
        """Simple content search with optional project filter."""
        return self.vector_store.search_content(
            query=query,
            metadata_filter=metadata_filter,
            n_results=10
        )
    
    def process_directory(self, directory_path: str, project_name: Optional[str] = None) -> List[str]:
        """Process all supported files in a directory."""
        content_hashes = []
        directory = Path(directory_path)
        
        try:
            for file_path in directory.rglob("*"):
                if file_path.suffix.lower() in ParserFactory.supported_extensions():
                    if content_hash := self.process_file(str(file_path), project_name):
                        content_hashes.append(content_hash)
            return content_hashes
        except Exception as e:
            logging.error(f"Error processing directory {directory_path}: {e}")
            return content_hashes
            
    async def process_directory_with_graph(self, directory_path: str, project_name: Optional[str] = None) -> List[str]:
        """Process all supported files in a directory using the graph-based approach."""
        content_hashes = []
        directory = Path(directory_path)
        
        try:
            for file_path in directory.rglob("*"):
                if file_path.suffix.lower() in ParserFactory.supported_extensions():
                    if content_hash := await self.process_file_with_graph(str(file_path), project_name):
                        content_hashes.append(content_hash)
            return content_hashes
        except Exception as e:
            logging.error(f"Error processing directory {directory_path}: {e}")
            return content_hashes
    
    def get_project_content(self, project_name: str) -> List[Dict]:
        """Get all content for a specific project."""
        return self.vector_store.search_content(
            metadata_filter={"project_name": project_name},
            n_results=1000
        )

    def clear_project_content(self, project_name: str):
        """Remove all content for a specific project."""
        try:
            results = self.get_project_content(project_name)
            content_hashes = {result["metadata"]["content_hash"] for result in results}
            for content_hash in content_hashes:
                self.vector_store.clear_content(content_hash=content_hash)
            logging.info(f"Cleared content for project: {project_name}")
        except Exception as e:
            logging.error(f"Error clearing project content: {e}")
