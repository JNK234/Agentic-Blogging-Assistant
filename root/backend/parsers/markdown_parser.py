"""
Simplified markdown parser that extracts content sections.
"""
from typing import Dict, List
import re

from .base import BaseParser, ContentStructure

class MarkdownParser(BaseParser):
    """Parser for Markdown files."""

    def parse(self) -> ContentStructure:
        """Parse markdown file into sections."""
        with open(self.file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        sections = []
        current_section = {"content": "", "type": "text"}
        
        # Split content by headers and code blocks
        lines = content.split('\n')
        in_code_block = False
        code_fence = ""
        
        for line in lines:
            # Handle code blocks
            if line.startswith('```'):
                if not in_code_block:
                    # Start new code block
                    if current_section["content"].strip():
                        sections.append(current_section)
                    code_fence = line[3:].strip()
                    current_section = {
                        "content": "",
                        "type": "code",
                        "language": code_fence
                    }
                    in_code_block = True
                else:
                    # End code block
                    sections.append(current_section)
                    current_section = {"content": "", "type": "text"}
                    in_code_block = False
                continue
            
            # Handle headers when not in code block
            if not in_code_block and line.startswith('#'):
                if current_section["content"].strip():
                    sections.append(current_section)
                current_section = {"content": line + "\n", "type": "text"}
            else:
                current_section["content"] += line + "\n"
        
        # Add final section
        if current_section["content"].strip():
            sections.append(current_section)
        
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
            content_type="markdown",
            metadata={}
        )
