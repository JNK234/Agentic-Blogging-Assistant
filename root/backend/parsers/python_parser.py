"""
Simplified Python parser that extracts content sections.
"""
from typing import Dict, List
import ast

from .base import BaseParser, ContentStructure

class PythonParser(BaseParser):
    """Parser for Python source files."""

    def parse(self) -> ContentStructure:
        """Parse Python file into sections."""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        sections = []
        try:
            tree = ast.parse(content)
            
            # Add module docstring if present
            if (docstring := ast.get_docstring(tree)):
                sections.append({
                    "content": docstring,
                    "type": "docstring"
                })
            
            # Process each node in the AST
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    # Get the source code for this node
                    start = node.lineno - 1
                    end = node.end_lineno
                    lines = content.split('\n')[start:end]
                    
                    sections.append({
                        "content": '\n'.join(lines),
                        "type": "class" if isinstance(node, ast.ClassDef) else "function"
                    })
                elif isinstance(node, ast.Assign):
                    # Include top-level assignments
                    start = node.lineno - 1
                    end = node.end_lineno
                    lines = content.split('\n')[start:end]
                    
                    sections.append({
                        "content": '\n'.join(lines),
                        "type": "assignment"
                    })
        except SyntaxError:
            # If parsing fails, treat the whole file as one section
            sections.append({
                "content": content,
                "type": "text"
            })
        
        # Extract main content and code segments from sections
        main_content = ""
        code_segments = []
        
        for section in sections:
            content = section.get("content", "")
            if section.get("type") in ["class", "function", "assignment"]:
                code_segments.append(content)
            else:
                main_content += content + "\n\n"
        
        return ContentStructure(
            main_content=main_content.strip(),
            code_segments=code_segments,
            content_type="python",
            metadata={}
        )
