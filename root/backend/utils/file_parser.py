import os
from typing import Dict, List, Optional, Union
import nbformat
from nbconvert import PythonExporter
import markdown2
import ast
from pathlib import Path

class FileParser:
    """Parser for extracting content from different file types (.ipynb, .md, .py)"""
    
    def parse_file(self, file_path: str) -> Dict[str, Union[str, List[Dict], Dict]]:
        """
        Main entry point for parsing different file types.
        
        Args:
            file_path (str): Path to the file to parse
            
        Returns:
            dict: Dictionary containing:
                - content: The parsed text content
                - code_blocks: List of {code, output} dictionaries
                - metadata: File-specific metadata
                
        Raises:
            ValueError: If file type is not supported
            FileNotFoundError: If file doesn't exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        file_ext = Path(file_path).suffix.lower()
        
        parsers = {
            '.ipynb': self.parse_notebook,
            '.md': self.parse_markdown,
            '.py': self.parse_python
        }
        
        if file_ext not in parsers:
            raise ValueError(f"Unsupported file type: {file_ext}")
            
        return parsers[file_ext](file_path)
    
    def parse_notebook(self, file_path: str) -> Dict[str, Union[str, List[Dict], Dict]]:
        """
        Parse Jupyter notebook files.
        
        Extracts:
        - Markdown content
        - Code cells with outputs
        - Execution order
        """
        try:
            notebook = nbformat.read(file_path, as_version=4)
            
            content = []
            code_blocks = []
            execution_order = []
            
            for cell in notebook.cells:
                if cell.cell_type == 'markdown':
                    content.append(cell.source)
                elif cell.cell_type == 'code':
                    # Store code cell content
                    code_block = {
                        'code': cell.source,
                        'language': 'python',
                        'output': '',
                        'context': '',
                        'line_number': len(content)  # Approximate location
                    }
                    
                    # Extract outputs if present
                    if hasattr(cell, 'outputs') and cell.outputs:
                        outputs = []
                        for output in cell.outputs:
                            if 'text' in output:
                                outputs.append(output.text)
                            elif 'data' in output:
                                if 'text/plain' in output.data:
                                    outputs.append(output.data['text/plain'])
                        code_block['output'] = '\n'.join(outputs)
                    
                    code_blocks.append(code_block)
                    execution_order.append(cell.execution_count or 0)
            
            return {
                'content': '\n\n'.join(content),
                'code_blocks': code_blocks,
                'metadata': {
                    'file_type': 'notebook',
                    'has_output': bool(code_blocks and any(block['output'] for block in code_blocks)),
                    'execution_order': execution_order
                }
            }
            
        except Exception as e:
            raise ValueError(f"Error parsing notebook: {str(e)}")
    
    def parse_markdown(self, file_path: str) -> Dict[str, Union[str, List[Dict], Dict]]:
        """
        Parse markdown files.
        
        Extracts:
        - Main content
        - Code blocks with language specification
        - Example outputs in code blocks
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Convert markdown to HTML to help with parsing
            html = markdown2.markdown(content, extras=['fenced-code-blocks'])
            
            # Extract code blocks
            code_blocks = []
            import re
            
            # Find code blocks with optional language specification
            code_pattern = r'```(\w+)?\n(.*?)```'
            matches = re.finditer(code_pattern, content, re.DOTALL)
            
            for match in matches:
                language = match.group(1) or 'text'
                code = match.group(2).strip()
                
                # Check if block contains output (separated by common patterns)
                code_parts = re.split(r'\n(?:Output|Result|>>>)\s*:\s*\n', code)
                
                code_block = {
                    'code': code_parts[0].strip(),
                    'language': language,
                    'output': code_parts[1].strip() if len(code_parts) > 1 else '',
                    'context': '',  # Could extract surrounding text if needed
                    'line_number': len(re.findall('\n', content[:match.start()]))
                }
                code_blocks.append(code_block)
            
            # Clean the content by removing unnecessary headers
            cleaned_content = self.clean_text(content)
            
            return {
                'content': cleaned_content,
                'code_blocks': code_blocks,
                'metadata': {
                    'file_type': 'markdown',
                    'has_output': bool(code_blocks and any(block['output'] for block in code_blocks)),
                    'execution_order': None
                }
            }
            
        except Exception as e:
            raise ValueError(f"Error parsing markdown: {str(e)}")
    
    def parse_python(self, file_path: str) -> Dict[str, Union[str, List[Dict], Dict]]:
        """
        Parse Python files.
        
        Extracts:
        - Docstrings
        - Comments
        - Code blocks
        - Example outputs from comments
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the Python file
            tree = ast.parse(content)
            
            # Extract docstrings and comments
            docstrings = []
            code_blocks = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    docstring = ast.get_docstring(node)
                    if docstring:
                        docstrings.append(docstring)
                        
                        # Look for example outputs in docstrings
                        if '>>>' in docstring or 'Example:' in docstring:
                            examples = self._extract_examples_from_docstring(docstring)
                            code_blocks.extend(examples)
            
            # Extract code blocks with potential outputs from comments
            source_lines = content.split('\n')
            current_block = []
            current_output = []
            in_output = False
            
            for i, line in enumerate(source_lines):
                stripped = line.strip()
                
                # Check for output markers in comments
                if stripped.startswith('# Output:') or stripped.startswith('# Result:'):
                    in_output = True
                    continue
                    
                if in_output and stripped.startswith('#'):
                    current_output.append(stripped[1:].strip())
                elif in_output:
                    # End of output section
                    if current_block and current_output:
                        code_blocks.append({
                            'code': '\n'.join(current_block),
                            'language': 'python',
                            'output': '\n'.join(current_output),
                            'context': '',
                            'line_number': i - len(current_block)
                        })
                    current_block = []
                    current_output = []
                    in_output = False
                
                if not in_output and not stripped.startswith('#'):
                    current_block.append(line)
            
            # Add any remaining block
            if current_block:
                code_blocks.append({
                    'code': '\n'.join(current_block),
                    'language': 'python',
                    'output': '',
                    'context': '',
                    'line_number': len(source_lines) - len(current_block)
                })
            
            return {
                'content': '\n\n'.join(docstrings),
                'code_blocks': code_blocks,
                'metadata': {
                    'file_type': 'python',
                    'has_output': bool(code_blocks and any(block['output'] for block in code_blocks)),
                    'execution_order': None
                }
            }
            
        except Exception as e:
            raise ValueError(f"Error parsing Python file: {str(e)}")
    
    def _extract_examples_from_docstring(self, docstring: str) -> List[Dict]:
        """Extract example code and output from docstrings."""
        examples = []
        lines = docstring.split('\n')
        current_code = []
        current_output = []
        in_example = False
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('>>>'):
                in_example = True
                current_code.append(stripped[3:].strip())
            elif stripped.startswith('...'):
                current_code.append(stripped[3:].strip())
            elif in_example and stripped:
                current_output.append(stripped)
            elif in_example and not stripped:
                if current_code:
                    examples.append({
                        'code': '\n'.join(current_code),
                        'language': 'python',
                        'output': '\n'.join(current_output),
                        'context': '',
                        'line_number': 0  # Docstring examples don't have line numbers
                    })
                current_code = []
                current_output = []
                in_example = False
        
        # Add any remaining example
        if current_code:
            examples.append({
                'code': '\n'.join(current_code),
                'language': 'python',
                'output': '\n'.join(current_output),
                'context': '',
                'line_number': 0
            })
        
        return examples
    
    def clean_text(self, text: str) -> str:
        """Clean and preprocess extracted text."""
        # Remove redundant whitespace
        text = ' '.join(text.split())
        
        # Remove unnecessary markdown headers
        text = re.sub(r'#{1,6}\s+', '', text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Standardize line endings
        text = text.replace('\r\n', '\n')
        
        return text.strip()
