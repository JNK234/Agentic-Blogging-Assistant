"""
Outline generator agent that uses content parsing agent for input processing.
"""
from typing import Optional, Tuple
import logging

from root.backend.prompts.prompt_manager import PromptManager
from root.backend.agents.outline_generator.graph import create_outline_graph
from root.backend.agents.outline_generator.state import OutlineState
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.base_agent import BaseGraphAgent
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

    async def generate_outline(
        self, 
        project_name: str,
        notebook_path: Optional[str] = None,
        markdown_path: Optional[str] = None,
        notebook_hash: Optional[str] = None,
        markdown_hash: Optional[str] = None,
        model=None  # For backward compatibility
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
                return final_outline_json, notebook_content, markdown_content
            else:
                msg = "Error: Final outline not found"
                logging.error(msg)
                return msg, None, None
                
        except Exception as e:
            msg = f"Error generating outline: {str(e)}"
            logging.exception(msg)
            return msg, None, None
