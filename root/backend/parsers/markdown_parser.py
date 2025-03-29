"""
Simplified markdown parser that extracts content sections.
"""
from typing import Dict, List
import re
import json

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
                # Extract the header level and text
                header_match = re.match(r'^(#+)\s+(.*?)$', line)
                if header_match:
                    header_level = len(header_match.group(1))
                    header_text = header_match.group(2).strip()
                    
                    if current_section["content"].strip():
                        sections.append(current_section)
                    
                    current_section = {
                        "content": line + "\n", 
                        "type": "text",
                        "header_level": header_level,
                        "header_text": header_text
                    }
                else:
                    current_section["content"] += line + "\n"
            else:
                current_section["content"] += line + "\n"
        
        # Add final section
        if current_section["content"].strip():
            sections.append(current_section)
        
        # Extract main content, code segments, and section headers from sections
        main_content = ""
        code_segments = []
        section_headers = []
        
        for section in sections:
            content = section.get("content", "")
            if section.get("type") == "code":
                code_segments.append(content)
            else:
                main_content += content + "\n\n"
                # Keep track of section headers
                if "header_text" in section and "header_level" in section:
                    section_headers.append({
                        "text": section["header_text"],
                        "level": section["header_level"]
                    })
        
        # Add section headers to metadata
        metadata = {
            "section_headers": json.dumps(section_headers)
        }
        
        return ContentStructure(
            main_content=main_content.strip(),
            code_segments=code_segments,
            content_type="markdown",
            metadata=metadata
        )
