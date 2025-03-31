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
from typing import Optional, Tuple, List, Dict, Any # Added Dict, Any
import logging
import hashlib
import json

from root.backend.prompts.prompt_manager import PromptManager
from root.backend.agents.outline_generator.graph import create_outline_graph
from root.backend.agents.outline_generator.state import OutlineState, FinalOutline
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.base_agent import BaseGraphAgent
from root.backend.services.vector_store_service import VectorStoreService
from root.backend.utils.serialization import serialize_object, to_json
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
    
    def _check_outline_cache(self, cache_key: str, project_name: str) -> Tuple[Optional[str], bool]:
        """Check if an outline exists in cache for the given parameters.
        
        Args:
            cache_key: The cache key to look up
            project_name: Project name for filtering
            
        Returns:
            Tuple of (Cached outline JSON string or None if not found, bool indicating if cache was used)
        """
        cached_outline = self.vector_store.retrieve_outline_cache(cache_key, project_name)
        return cached_outline, cached_outline is not None
        
    async def generate_outline(
        self, 
        project_name: str,
        notebook_path: Optional[str] = None,
        markdown_path: Optional[str] = None,
        notebook_hash: Optional[str] = None,
        markdown_hash: Optional[str] = None,
        model=None,  # For backward compatibility
        use_cache: bool = True  # Whether to use cached outlines
    ) -> Tuple[Optional[Dict[str, Any]], Optional[ContentStructure], Optional[ContentStructure], bool]: # Return type changed
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
            Tuple of (outline Dict or error Dict, notebook content, markdown content, was_cached)
        """
        # Use the model passed to the constructor if no override is provided
        model_to_use = model if model is not None else self.llm
        logging.info(f"Generating outline for project: {project_name}")
        was_cached = False
        
        # Process input files
        notebook_content = None
        markdown_content = None
        
        # Verify we have at least one source of content
        if not (notebook_path or notebook_hash or markdown_path or markdown_hash):
            error_msg = "At least one content source (notebook or markdown) is required"
            logging.error(error_msg)
            # Return structured error
            return {"error": error_msg, "details": "Missing content source"}, None, None, False

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
                # Continue with markdown if available
        
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
        
        # Ensure we have at least one processed content
        if not notebook_content and not markdown_content:
            error_msg = "Failed to process any content files"
            logging.error(error_msg)
            # Return structured error
            return {"error": error_msg, "details": "Content processing failed"}, None, None, False

        # Check cache if enabled
        if use_cache:
            cache_key = self._create_cache_key(project_name, notebook_hash, markdown_hash)
            cached_outline_json, cache_found = self._check_outline_cache(cache_key, project_name)

            if cache_found:
                logging.info(f"Using cached outline for project: {project_name}")
                try:
                    # Attempt to parse cached JSON
                    cached_outline_data = json.loads(cached_outline_json)
                    # Return parsed data, notebook/markdown content, and cache status
                    return cached_outline_data, notebook_content, markdown_content, True
                except json.JSONDecodeError:
                    logging.error(f"Failed to parse cached outline JSON for key {cache_key}. Regenerating.")
                    # Proceed to regenerate if cache is invalid

        # Prepare initial state dictionary for the graph
        # Ensure all keys are present, even if None, for LangGraph compatibility
        initial_state_dict = {
            "notebook_content": notebook_content,
            "markdown_content": markdown_content,
            "model": model_to_use,
            "analysis_result": None,
            "difficulty_level": None,
            "prerequisites": None,
            "outline_structure": None,
            "final_outline": None
        }

        # Execute graph
        try:
            logging.info("Executing outline generation graph...")
            # Pass the dictionary to run_graph
            state = await self.run_graph(initial_state_dict)
            logging.info("Outline generation completed successfully")

            # Check the final state dictionary returned by the graph
            if state and isinstance(state, dict) and state.get('final_outline'):
                final_outline_obj = state['final_outline']

                # Ensure it's the expected type before proceeding
                if not isinstance(final_outline_obj, FinalOutline):
                     logging.error(f"Graph returned unexpected type for final_outline: {type(final_outline_obj)}")
                     # Return structured error
                     return {"error": "Outline generation failed", "details": "Invalid internal state"}, None, None, False

                # Serialize the FinalOutline object to a dictionary
                outline_data = serialize_object(final_outline_obj) # Use existing serialization

                # Cache the result if caching is enabled
                if use_cache and ( notebook_hash or markdown_hash ):
                    cache_key = self._create_cache_key(project_name, notebook_hash, markdown_hash)
                    source_hashes = [h for h in [notebook_hash, markdown_hash] if h]
                    # Convert the dict back to JSON string for storage
                    outline_json_str = to_json(outline_data)
                    logging.info(f"Caching outline with key {cache_key}")
                    self.vector_store.store_outline_cache(
                        outline_json=outline_json_str,
                        cache_key=cache_key,
                        project_name=project_name,
                        source_hashes=source_hashes
                    )

                # Return the serialized dictionary, content, and cache status
                return outline_data, notebook_content, markdown_content, False
            else:
                msg = "Error: Final outline not found in graph state"
                logging.error(msg)
                # Return structured error
                return {"error": "Outline generation failed", "details": msg}, None, None, False

        except Exception as e:
            msg = f"Error generating outline: {str(e)}"
            logging.exception(msg)
            # Return structured error including exception type
            return {"error": "Outline generation failed", "details": msg, "type": type(e).__name__}, None, None, False

    def clear_outline_cache(self, project_name: Optional[str] = None):
        """Clear cached outlines for a project or all projects.
        
        Args:
            project_name: Optional project name to clear cache for
        """
        self.vector_store.clear_outline_cache(project_name)
