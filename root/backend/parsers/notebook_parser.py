"""
Simplified Jupyter Notebook parser using LangChain.
"""
from typing import Dict, List
from langchain_community.document_loaders import NotebookLoader

from .base import BaseParser, ContentStructure

class NotebookParser(BaseParser):
    """Parser for Jupyter Notebook files."""

    def parse(self) -> ContentStructure:
        """Parse notebook file into sections using LangChain."""
        # Use LangChain's NotebookLoader to parse the notebook
        loader = NotebookLoader(
            str(self.file_path),
            include_outputs=True,
            max_output_length=1000
        )
        
        documents = loader.load()
        sections = []
        
        for doc in documents:
            # Each document represents a cell
            if not doc.page_content.strip():
                continue
                
            # Determine cell type from metadata
            cell_type = doc.metadata.get("cell_type", "unknown")
            
            section = {
                "content": doc.page_content,
                "type": cell_type
            }
            
            # Include source and output info for code cells
            if cell_type == "code":
                source = doc.metadata.get("source", "")
                outputs = doc.metadata.get("outputs", [])
                
                if outputs:
                    output_text = []
                    for output in outputs:
                        if "text" in output:
                            output_text.append(output["text"])
                        elif "data" in output and "text/plain" in output["data"]:
                            output_text.append(output["data"]["text/plain"])
                    
                    if output_text:
                        section["content"] = f"{source}\n# Output:\n{''.join(output_text)}"
            
            sections.append(section)
        
        return ContentStructure(
            sections=sections,
            content_type="jupyter_notebook"
        )
