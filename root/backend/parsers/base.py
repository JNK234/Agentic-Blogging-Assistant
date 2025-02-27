"""
Simplified base parser interface for file content extraction.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path

@dataclass
class ContentStructure:
    """Represents parsed file content with sections."""
    main_content: str  # Main content extracted from the file
    code_segments: List[str]  # List of code segments extracted from the file
    content_type: str  # Type of content (markdown, python, notebook)
    metadata: Optional[Dict[str, str]] = field(default_factory=dict)  # Optional metadata about the content

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
