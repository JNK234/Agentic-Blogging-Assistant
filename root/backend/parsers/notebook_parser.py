"""
Simplified Jupyter Notebook parser using LangChain.
"""
from typing import Dict, List
from langchain_community.document_loaders import NotebookLoader
import logging

from .base import BaseParser, ContentStructure

class NotebookParser(BaseParser):
    """Parser for Jupyter Notebook files."""
    
    # Constants for truncation
    MAX_CELL_LENGTH = 30000  # Maximum length for a single cell
    MAX_OUTPUT_LENGTH = 1000  # Maximum length for cell outputs
    MAX_TOTAL_LENGTH = 20000  # Maximum total length for the notebook
    
    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text to max_length while trying to preserve complete sentences."""
        if len(text) <= max_length:
            return text
            
        # Try to find a sentence end within the last 100 characters of the limit
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        
        # Use the latest sentence or line break as the truncation point
        truncation_point = max(last_period, last_newline)
        if truncation_point > max_length - 100:  # Only use if it's near the end
            truncated = text[:truncation_point + 1]
        
        logging.info(f"Truncated content from {len(text)} to {len(truncated)} characters")
        return truncated.strip()

    def parse(self) -> ContentStructure:
        """Parse notebook file into sections using LangChain."""
        # Use LangChain's NotebookLoader to parse the notebook
        loader = NotebookLoader(
            str(self.file_path),
            include_outputs=True,
            max_output_length=self.MAX_OUTPUT_LENGTH
        )
        
        documents = loader.load()
        sections = []
        total_length = 0
        
        for doc in documents:
            # Each document represents a cell
            if not doc.page_content.strip():
                continue
                
            # Determine cell type from metadata
            cell_type = doc.metadata.get("cell_type", "unknown")
            
            # Get and truncate cell content
            content = doc.page_content
            content = self._truncate_text(content, self.MAX_CELL_LENGTH)
            
            section = {
                "content": content,
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
                        combined_output = ''.join(output_text)
                        # Truncate the combined output
                        truncated_output = self._truncate_text(combined_output, self.MAX_OUTPUT_LENGTH)
                        section["content"] = f"{source}\n# Output:\n{truncated_output}"
            
            # Check total length before adding new section
            new_total_length = total_length + len(section["content"])
            if new_total_length > self.MAX_TOTAL_LENGTH:
                logging.warning(f"Notebook content exceeded maximum length of {self.MAX_TOTAL_LENGTH} characters. Truncating remaining cells.")
                break
                
            sections.append(section)
            total_length = new_total_length
        
        if total_length >= self.MAX_TOTAL_LENGTH:
            logging.warning(f"Notebook was truncated. Original size: {total_length}, Truncated to: {self.MAX_TOTAL_LENGTH}")
        
        # Extract main content and code segments from sections
        main_content = ""
        code_segments = []
        
        for section in sections:
            content = section.get("content", "")
            if section.get("type") == "code":
                code_segments.append(content)
            else:
                main_content += content + "\n\n"
        
        return ContentStructure(
            main_content=main_content.strip(),
            code_segments=code_segments,
            content_type="jupyter_notebook",
            metadata={
                "total_length": total_length,
                "was_truncated": total_length >= self.MAX_TOTAL_LENGTH,
                "num_cells": len(sections)
            }
        )
