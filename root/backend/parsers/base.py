"""
Simplified base parser interface for file content extraction.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List
from pathlib import Path

@dataclass
class ContentStructure:
    """Represents parsed file content with sections."""
    sections: List[Dict[str, str]]  # Each section has 'content' and optional 'type'
    content_type: str  # Type of content (markdown, python, notebook)

class BaseParser(ABC):
    """Base parser for extracting content from files."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        if not self._is_valid_file():
            raise ValueError(f"Invalid or unreadable file: {file_path}")
    
    def _is_valid_file(self) -> bool:
        """Check if file exists and is readable."""
        path = Path(self.file_path)
        return path.exists() and path.is_file()
    
    @abstractmethod
    def parse(self) -> ContentStructure:
        """Parse file and return content structure."""
        pass
