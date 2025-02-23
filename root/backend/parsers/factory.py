"""
Factory class for creating appropriate parsers based on file type.
"""
from pathlib import Path
from typing import Type

from .base import BaseParser
from .markdown_parser import MarkdownParser
from .python_parser import PythonParser
from .notebook_parser import NotebookParser

class ParserFactory:
    """Factory class for creating file parsers."""
    
    _FILE_EXTENSIONS = {
        '.md': MarkdownParser,
        '.markdown': MarkdownParser,
        '.py': PythonParser,
        '.ipynb': NotebookParser
    }
    
    @classmethod
    def get_parser(cls, file_path: str) -> BaseParser:
        """Get appropriate parser for the given file.
        
        Args:
            file_path (str): Path to the file to be parsed
        
        Returns:
            BaseParser: Instance of appropriate parser for the file type
        
        Raises:
            ValueError: If file type is not supported
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext not in cls._FILE_EXTENSIONS:
            supported = ", ".join(cls._FILE_EXTENSIONS.keys())
            raise ValueError(
                f"Unsupported file type: {file_ext}. "
                f"Supported types are: {supported}"
            )
        
        parser_class = cls._FILE_EXTENSIONS[file_ext]
        return parser_class(file_path)
    
    @classmethod
    def register_parser(
        cls, 
        extension: str, 
        parser_class: Type[BaseParser]
    ) -> None:
        """Register a new parser for a file extension.
        
        Args:
            extension (str): File extension (including dot)
            parser_class (Type[BaseParser]): Parser class to use
        
        Raises:
            ValueError: If extension is invalid or parser class is not a BaseParser
        """
        if not extension.startswith('.'):
            raise ValueError("Extension must start with a dot")
        
        if not issubclass(parser_class, BaseParser):
            raise ValueError("Parser class must inherit from BaseParser")
        
        cls._FILE_EXTENSIONS[extension.lower()] = parser_class
    
    @classmethod
    def supported_extensions(cls) -> list[str]:
        """Get list of supported file extensions.
        
        Returns:
            list[str]: List of supported file extensions
        """
        return list(cls._FILE_EXTENSIONS.keys())
