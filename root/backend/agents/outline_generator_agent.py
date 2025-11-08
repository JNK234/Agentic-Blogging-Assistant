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
from root.backend.services.persona_service import PersonaService
from root.backend.utils.serialization import serialize_object, to_json
from root.backend.parsers.base import ContentStructure

logging.basicConfig(level=logging.INFO)

class OutlineGeneratorAgent(BaseGraphAgent):
    def __init__(self, model, content_parser, vector_store: VectorStoreService, persona_service: PersonaService = None, sql_project_manager=None): # Added sql_project_manager parameter
        super().__init__(
            llm=model,
            tools=[],  # Add any needed tools
            state_class=OutlineState,
            verbose=True
        )
        self.prompt_manager = PromptManager()
        self.content_parser = content_parser  # Use the passed content parser
        self.vector_store = vector_store  # Use the passed vector_store instance
        self.persona_service = persona_service or PersonaService() # Initialize persona service
        self.sql_project_manager = sql_project_manager  # SQL project manager for persistence
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

    def _create_cache_key(self, project_name: str, notebook_hash: Optional[str], markdown_hash: Optional[str], 
                         user_guidelines: Optional[str], length_preference: Optional[str], 
                         custom_length: Optional[int], writing_style: Optional[str]) -> str:
        """Create a deterministic cache key from input parameters, including user guidelines and length preferences.
        
        Args:
            project_name: Name of the project
            notebook_hash: Hash of notebook content (or None)
            markdown_hash: Hash of markdown content (or None)
            user_guidelines: Optional user-provided guidelines for generation
            length_preference: Optional length preference
            custom_length: Optional custom length
            writing_style: Optional writing style
            
        Returns:
            A unique cache key string
        """
        # Create a string with all parameters
        guidelines_hash_part = hashlib.sha256((user_guidelines or "").encode()).hexdigest() if user_guidelines else "no_guidelines"
        
        key_parts = [
            f"project:{project_name}",
            f"notebook:{notebook_hash or 'none'}",
            f"markdown:{markdown_hash or 'none'}",
            f"guidelines_hash:{guidelines_hash_part}",
            f"length_pref:{length_preference or 'auto'}",
            f"custom_len:{custom_length or 0}",
            f"style:{writing_style or 'balanced'}"
        ]
        
        # Join and hash to create a deterministic key
        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()
    
    def _calculate_intelligent_length(self, content_analysis, length_preference: Optional[str], 
                                    custom_length: Optional[int], writing_style: Optional[str]) -> int:
        """Calculate intelligent blog length based on content analysis and user preferences.
        
        Args:
            content_analysis: ContentAnalysis object with AI-generated length suggestions
            length_preference: User's preferred length category
            custom_length: Custom length if specified
            writing_style: User's writing style preference
            
        Returns:
            Calculated target blog length in words
        """
        # Start with AI-suggested length from content analysis
        base_length = getattr(content_analysis, 'suggested_blog_length', 1500)
        
        # Override with custom length if specified
        if length_preference == "Custom" and custom_length:
            return custom_length
        
        # Apply user length preference if specified
        if length_preference and length_preference != "Auto-detect (Recommended)":
            if length_preference == "Short (800-1200)":
                base_length = min(base_length, 1200)
                base_length = max(base_length, 800)
            elif length_preference == "Medium (1200-2000)":
                base_length = min(base_length, 2000)
                base_length = max(base_length, 1200)
            elif length_preference == "Long (2000-3000)":
                base_length = min(base_length, 3000)
                base_length = max(base_length, 2000)
            elif length_preference == "Very Long (3000+)":
                base_length = max(base_length, 3000)
        
        # Adjust based on writing style
        if writing_style == "Concise & Focused":
            base_length = int(base_length * 0.8)  # 20% shorter
        elif writing_style == "Comprehensive & Detailed":
            base_length = int(base_length * 1.2)  # 20% longer
        # "Balanced" style uses base length as-is
        
        # Ensure reasonable bounds
        base_length = max(base_length, 500)   # Minimum 500 words
        base_length = min(base_length, 5000)  # Maximum 5000 words
        
        logging.info(f"Calculated intelligent blog length: {base_length} words "
                    f"(preference: {length_preference}, style: {writing_style})")
        
        return base_length
    
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
        user_guidelines: Optional[str] = None, # Added
        length_preference: Optional[str] = None, # Added
        custom_length: Optional[int] = None, # Added
        writing_style: Optional[str] = None, # Added
        persona: Optional[str] = None, # Added persona parameter
        model=None,  # For backward compatibility
        use_cache: bool = True,  # Whether to use cached outlines
        cost_aggregator=None,
        project_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[ContentStructure], Optional[ContentStructure], bool]: # Return type changed
        """
        Generates a blog outline using parsed content from files.

        Args:
            project_name: Name of the project for content organization
            notebook_path: Optional path to Jupyter notebook
            markdown_path: Optional path to markdown file
            notebook_hash: Optional content hash for notebook (if already processed)
            markdown_hash: Optional content hash for markdown (if already processed)
            user_guidelines: Optional user-provided guidelines for generation
            length_preference: Optional user's preferred blog length category
            custom_length: Optional custom target word count 
            writing_style: Optional user's preferred writing style
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
        if use_cache: # This 'use_cache' is from the generate_outline signature, distinct from the 'regenerate' flag logic
            cache_key = self._create_cache_key(project_name, notebook_hash, markdown_hash, user_guidelines, 
                                             length_preference, custom_length, writing_style)
            cached_outline_json, cache_found = self._check_outline_cache(cache_key, project_name)

            if cache_found:
                logging.info(f"Using cached outline for project: {project_name} with key: {cache_key}")
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
        initial_state = OutlineState(
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=model_to_use,
            analysis_result=None,
            difficulty_level=None,
            prerequisites=None,
            outline_structure=None,
            final_outline=None,
            user_guidelines=user_guidelines,
            length_preference=length_preference,
            custom_length=custom_length,
            writing_style=writing_style,
            persona=persona or "neuraforge",  # Pass persona with default
            project_name=project_name,
            project_id=project_id,
            cost_aggregator=cost_aggregator,
            current_stage="outline_generation",
            sql_project_manager=self.sql_project_manager  # Pass SQL manager for persistence
        )

        # Execute graph
        try:
            logging.info("Executing outline generation graph...")
            # Pass the state to run_graph
            state = await self.run_graph(initial_state)
            logging.info("Outline generation completed successfully")

            if isinstance(state, OutlineState):
                final_outline_obj = state.final_outline
                if state.cost_aggregator:
                    state.update_cost_summary()
                state_dict = state.model_dump()
            elif isinstance(state, dict):
                final_outline_obj = state.get('final_outline')
                state_dict = state
            else:
                logging.error("Graph returned unexpected state type for outline generation")
                return {"error": "Outline generation failed", "details": "Invalid internal state"}, None, None, False

            if final_outline_obj is None:
                msg = "Error: Final outline not found in graph state"
                logging.error(msg)
                return {"error": "Outline generation failed", "details": msg}, None, None, False

            if not isinstance(final_outline_obj, FinalOutline):
                logging.info("Attempting to rehydrate final outline from serialized form")
                try:
                    final_outline_obj = FinalOutline.model_validate(final_outline_obj)
                except Exception as validation_err:
                    logging.error(
                        f"Graph returned unexpected type for final_outline: {type(final_outline_obj)} | "
                        f"Error: {validation_err}"
                    )
                    return {
                        "error": "Outline generation failed",
                        "details": "Invalid final outline structure returned by graph"
                    }, None, None, False

            outline_data = serialize_object(final_outline_obj)

            if use_cache and (notebook_hash or markdown_hash):
                cache_key = self._create_cache_key(
                    project_name,
                    notebook_hash,
                    markdown_hash,
                    user_guidelines,
                    length_preference,
                    custom_length,
                    writing_style
                )
                source_hashes = [h for h in [notebook_hash, markdown_hash] if h]
                outline_json_str = to_json(outline_data)
                logging.info(f"Caching outline with key {cache_key}")
                self.vector_store.store_outline_cache(
                    outline_json=outline_json_str,
                    cache_key=cache_key,
                    project_name=project_name,
                    source_hashes=source_hashes
                )

            return outline_data, notebook_content, markdown_content, False

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
