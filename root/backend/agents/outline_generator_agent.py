"""
Outline generator agent that uses content parsing agent for input processing.
"""
from typing import Optional, Tuple
import logging

from root.backend.prompts.prompt_manager import PromptManager
from root.backend.agents.outline_generator.graph import create_outline_graph
from root.backend.agents.outline_generator.state import OutlineState
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from ..parsers import ContentStructure

logging.basicConfig(level=logging.INFO)

class OutlineGeneratorAgent:
    def __init__(self):
        self.prompt_manager = PromptManager()
        self.graph = create_outline_graph()
        self.content_parser = ContentParsingAgent()

    def _get_processed_content(self, content_hash: str, file_type: str) -> Optional[ContentStructure]:
        results = self.content_parser.search_content(
            metadata_filter={
                "content_hash": content_hash,
                "file_type": file_type
            }
        )
        if not results:
            logging.warning(f"No content found for hash {content_hash}")
            return None
            
        return ContentStructure(
            sections=[{"content": r["content"]} for r in results],
            content_type="jupyter_notebook" if file_type == ".ipynb" else "markdown"
        )

    async def generate_outline(
        self, 
        project_name: str,
        model,
        notebook_path: Optional[str] = None,
        markdown_path: Optional[str] = None
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Generates a blog outline using parsed content from files.
        
        Args:
            project_name: Name of the project for content organization
            model: Language model to use for generation
            notebook_path: Optional path to Jupyter notebook
            markdown_path: Optional path to markdown file
            
        Returns:
            Tuple of (outline JSON, notebook content, markdown content)
        """
        logging.info(f"Generating outline for project: {project_name}")
        
        # Process input files
        notebook_content = None
        markdown_content = None
        
        if notebook_path:
            logging.info(f"Processing notebook: {notebook_path}")
            notebook_content_hash = self.content_parser.process_file(notebook_path, project_name)
            if notebook_content_hash:
                notebook_content = self._get_processed_content(notebook_content_hash, ".ipynb")
            else:
                logging.error(f"Failed to process notebook: {notebook_path}")
        
        if markdown_path:
            logging.info(f"Processing markdown: {markdown_path}")
            markdown_content_hash = self.content_parser.process_file(markdown_path, project_name)
            if markdown_content_hash:
                markdown_content = self._get_processed_content(markdown_content_hash, ".md")
            else:
                logging.error(f"Failed to process markdown: {markdown_path}")
                
        # print(notebook_content)
        # print(markdown_content)
        
        # Initialize state
        initial_state = OutlineState(
            notebook_content=notebook_content,
            markdown_content=markdown_content,
            model=model
        )

        # Execute graph
        try:
            logging.info("Executing outline generation graph...")
            state = await self.graph.ainvoke(initial_state)
            logging.info("Outline generation completed successfully")
            
            if state.final_outline:
                final_outline_json = state.final_outline.model_dump_json(indent=2)
                return final_outline_json, notebook_content, markdown_content
            else:
                msg = "Error: Final outline not found"
                logging.error(msg)
                return msg, None, None
                
        except Exception as e:
            msg = f"Error generating outline: {str(e)}"
            logging.exception(msg)
            return msg, None, None
