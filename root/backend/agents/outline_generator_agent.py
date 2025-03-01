"""
Outline generator agent that uses content parsing agent for input processing.
Includes caching of generated outlines for efficient retrieval.
"""
from typing import Optional, Tuple, List
import logging
import hashlib
import json

from root.backend.prompts.prompt_manager import PromptManager
from root.backend.agents.outline_generator.graph import create_outline_graph
from root.backend.agents.outline_generator.state import OutlineState
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.base_agent import BaseGraphAgent
from root.backend.services.vector_store_service import VectorStoreService
from ..parsers import ContentStructure

logging.basicConfig(level=logging.INFO) 

class OutlineGeneratorAgent(BaseGraphAgent):
    def __init__(self, model, content_parser):
        super().__init__(
            llm=model,
            tools=[],  # Add any needed tools
            state_class=OutlineState,
            verbose=True
        )
        self.prompt_manager = PromptManager()
        self.content_parser = content_parser  # Use the passed content parser
        self.vector_store = VectorStoreService()  # For caching outlines
        self._initialized = False
        
    async def initialize(self):
        """Public method to initialize the agent and its dependencies."""
        if self._initialized:
            logging.info("Agent already initialized")
            return
            
        # Initialize outline generator graph
        self.graph = await create_outline_graph()
        
        # Initialize content parser
        await self.content_parser.initialize()
        
        self._initialized = True
        logging.info("OutlineGeneratorAgent fully initialized")

    def _get_processed_content(self, content_hash: str, file_type: str, query: Optional[str] = None) -> Optional[ContentStructure]:
        """Get processed content from the content parsing agent.
        
        Args:
            content_hash: Hash of the content to retrieve
            file_type: Type of file (.ipynb, .md, etc.)
            query: Optional query to filter content
            
        Returns:
            ContentStructure object or None if not found
        """
        metadata_filter = {
            "content_hash": content_hash,
            "file_type": file_type
        }
        
        results = self.content_parser.search_content(
            metadata_filter=metadata_filter,
            query=query
        )
        
        if not results:
            logging.warning(f"No content found for hash {content_hash}")
            return None
        
        # Process and organize the content
        main_content = []
        code_segments = []
        metadata = results[0].get("metadata", {})
        
        for result in results:
            content_type = result.get("metadata", {}).get("content_type")
            content = result.get("content", "").strip()
            
            # print(f"Content type: {content_type}")
            # print(f"Content: {content}")
            
            if not content:
                continue
            
            if content_type == "code":
                code_segments.append(content)
            else:
                main_content.append(content)
        
        return ContentStructure(
            main_content="\n".join(main_content),
            code_segments=code_segments,
            metadata=metadata,
            content_type=metadata.get("content_type", "unknown")
        )

    def _create_cache_key(self, project_name: str, notebook_hash: Optional[str], markdown_hash: Optional[str]) -> str:
        """Create a deterministic cache key from input parameters.
        
        Args:
            project_name: Name of the project
            notebook_hash: Hash of notebook content (or None)
            markdown_hash: Hash of markdown content (or None)
            
        Returns:
            A unique cache key string
        """
        # Create a string with all parameters
        key_parts = [
            f"project:{project_name}",
            f"notebook:{notebook_hash or 'none'}",
            f"markdown:{markdown_hash or 'none'}"
        ]
        
        # Join and hash to create a deterministic key
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _check_outline_cache(self, cache_key: str, project_name: str) -> Optional[str]:
        """Check if an outline exists in cache for the given parameters.
        
        Args:
            cache_key: The cache key to look up
            project_name: Project name for filtering
            
        Returns:
            Cached outline JSON string or None if not found
        """
        return self.vector_store.retrieve_outline_cache(cache_key, project_name)
        
    async def generate_outline(
        self, 
        project_name: str,
        notebook_path: Optional[str] = None,
        markdown_path: Optional[str] = None,
        notebook_hash: Optional[str] = None,
        markdown_hash: Optional[str] = None,
        model=None,  # For backward compatibility
        use_cache: bool = True  # Whether to use cached outlines
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Generates a blog outline using parsed content from files.
        
        Args:
            project_name: Name of the project for content organization
            notebook_path: Optional path to Jupyter notebook
            markdown_path: Optional path to markdown file
            notebook_hash: Optional content hash for notebook (if already processed)
            markdown_hash: Optional content hash for markdown (if already processed)
            model: Optional model override (for backward compatibility)
            use_cache: Whether to use cached outlines (default: True)
            
        Returns:
            Tuple of (outline JSON, notebook content, markdown content)
        """
        # Use the model passed to the constructor if no override is provided
        model_to_use = model if model is not None else self.llm
        logging.info(f"Generating outline for project: {project_name}")
        
        # Process input files
        notebook_content = None
        markdown_content = None
        
        # Process notebook content
        if notebook_hash:
            logging.info(f"Using provided notebook hash: {notebook_hash}")
            notebook_content = self._get_processed_content(notebook_hash, ".ipynb")
        elif notebook_path:
            logging.info(f"Processing notebook: {notebook_path}")
            try:
                # Use async method if available
                notebook_hash = await self.content_parser.process_file_with_graph(notebook_path, project_name)
                if notebook_hash:
                    notebook_content = self._get_processed_content(notebook_hash, ".ipynb")
                else:
                    # Fall back to synchronous method
                    notebook_hash = self.content_parser.process_file(notebook_path, project_name)
                    if notebook_hash:
                        notebook_content = self._get_processed_content(notebook_hash, ".ipynb")
                    else:
                        logging.error(f"Failed to process notebook: {notebook_path}")
            except Exception as e:
                logging.error(f"Error processing notebook: {str(e)}")
        
        # Process markdown content
        if markdown_hash:
            logging.info(f"Using provided markdown hash: {markdown_hash}")
            markdown_content = self._get_processed_content(markdown_hash, ".md")
        elif markdown_path:
            logging.info(f"Processing markdown: {markdown_path}")
            try:
                # Use async method if available
                markdown_hash = await self.content_parser.process_file_with_graph(markdown_path, project_name)
                if markdown_hash:
                    markdown_content = self._get_processed_content(markdown_hash, ".md")
                else:
                    # Fall back to synchronous method
                    markdown_hash = self.content_parser.process_file(markdown_path, project_name)
                    if markdown_hash:
                        markdown_content = self._get_processed_content(markdown_hash, ".md")
                    else:
                        logging.error(f"Failed to process markdown: {markdown_path}")
            except Exception as e:
                logging.error(f"Error processing markdown: {str(e)}")
        
        # Check cache if enabled
        if use_cache:
            cache_key = self._create_cache_key(project_name, notebook_hash, markdown_hash)
            cached_outline = self._check_outline_cache(cache_key, project_name)
            
            if cached_outline:
                logging.info(f"Using cached outline for project: {project_name}")
                return cached_outline, notebook_content, markdown_content
        
        # Initialize state
        initial_state = OutlineState(
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=model_to_use,
            analysis_result=None,
            difficulty_level=None,
            prerequisites=None,
            outline_structure=None,
            final_outline=None
        )

        # Execute graph
        try:
            logging.info("Executing outline generation graph...")
            state = await self.run_graph(initial_state)
            logging.info("Outline generation completed successfully")
            
            if state['final_outline']:
                final_outline_json = state['final_outline']
                
                # Cache the result if caching is enabled
                if use_cache and notebook_hash and markdown_hash:
                    cache_key = self._create_cache_key(project_name, notebook_hash, markdown_hash)
                    source_hashes = [h for h in [notebook_hash, markdown_hash] if h]
                    
                    # Check if final_outline_json is a FinalOutline instance and convert to JSON string
                    from root.backend.agents.outline_generator.state import FinalOutline
                    if isinstance(final_outline_json, FinalOutline):
                        # Use the to_json method to convert to a JSON string
                        outline_json_str = final_outline_json.to_json()
                    elif isinstance(final_outline_json, str):
                        # Already a string, use as is
                        outline_json_str = final_outline_json
                    else:
                        # Try to convert to string
                        outline_json_str = str(final_outline_json)
                        
                    logging.info(f"Caching outline with key {cache_key}")
                    self.vector_store.store_outline_cache(
                        outline_json=outline_json_str,
                        cache_key=cache_key,
                        project_name=project_name,
                        source_hashes=source_hashes
                    )
                
                return final_outline_json, notebook_content, markdown_content
            else:
                msg = "Error: Final outline not found"
                logging.error(msg)
                return msg, None, None
                
        except Exception as e:
            msg = f"Error generating outline: {str(e)}"
            logging.exception(msg)
            return msg, None, None
            
    def clear_outline_cache(self, project_name: Optional[str] = None):
        """Clear cached outlines for a project or all projects.
        
        Args:
            project_name: Optional project name to clear cache for
        """
        self.vector_store.clear_outline_cache(project_name)
