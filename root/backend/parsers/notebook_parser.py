"""
Simplified Jupyter Notebook parser using LangChain.
"""
from typing import Dict, List
from langchain_community.document_loaders import NotebookLoader
import logging

from .base import BaseParser, ContentStructure

class NotebookParser(BaseParser):
    """
    Parser for Jupyter Notebook files using LangChain's NotebookLoader.
    Extracts the combined content of all cells. Relies on downstream nodes
    for structural splitting and chunking.
    """
    # Default max output length for NotebookLoader
    MAX_OUTPUT_LENGTH = 1000

    def parse(self) -> ContentStructure:
        """Parse notebook file using LangChain's NotebookLoader."""
        try:
            # Use LangChain's NotebookLoader to parse the notebook
            loader = NotebookLoader(
                str(self.file_path),
                include_outputs=True, # Include cell outputs
                max_output_length=self.MAX_OUTPUT_LENGTH, # Limit output length
                remove_newline=True # Removes excessive newlines
            )
            
            # Load documents (each document usually represents a cell)
            documents = loader.load()
            
            # Concatenate the page_content of all loaded documents
            # Add a simple separator to hint at cell boundaries for splitters
            combined_content = "\n\n---\n\n".join([doc.page_content for doc in documents if doc.page_content.strip()])
            
            # Basic metadata (more can be added in prepare_metadata node)
            metadata = {
                "num_cells_loaded": len(documents)
            }

            # Return the combined content as main_content.
            # The chunk_content node will handle splitting based on content type (code vs markdown).
            return ContentStructure(
                main_content=combined_content,
                code_segments=[], # Let chunk_content handle code identification/splitting
                content_type="jupyter_notebook",
                metadata=metadata
            )
        except Exception as e:
            logging.exception(f"Error parsing notebook file {self.file_path}: {e}")
            # Return an empty structure on error
            return ContentStructure(
                main_content="",
                code_segments=[],
                content_type="jupyter_notebook",
                metadata={"error": f"Failed to parse notebook: {e}"}
            )
