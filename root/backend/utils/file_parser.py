from typing import Dict, List, Optional, Union
from pydantic import BaseModel
import nbformat
import markdown2
import ast
from pathlib import Path
import re
import logging

logging.basicConfig(level=logging.INFO)

# Data Models
class Location(BaseModel):
    section: str
    line_number: Optional[int] = None
    context: str = ""

class CodeSegment(BaseModel):
    code: str
    language: str
    output: Optional[str] = None
    explanation: Optional[str] = None
    dependencies: List[str] = []
    location: Location

class ContentMetadata(BaseModel):
    file_type: str
    title: Optional[str] = None
    topics: List[str] = []
    complexity_indicators: List[str] = []
    prerequisites: List[str] = []

class ContentGraph(BaseModel):
    topic_hierarchy: Dict[str, List[str]] = {}
    code_dependencies: Dict[str, List[str]] = {}
    concept_relationships: Dict[str, List[str]] = {}

class ParsedContent(BaseModel):
    main_content: str
    code_segments: List[CodeSegment] = []
    metadata: ContentMetadata
    content_graph: ContentGraph

class FileParser:
    def parse_file(self, file_path: str) -> ParsedContent:
        logging.info(f"Parsing file: {file_path}")
        if not Path(file_path).exists():
            msg = f"Error: File not found at path: {file_path}"
            logging.error(msg)
            raise FileNotFoundError(msg)
            
        file_ext = Path(file_path).suffix.lower()
        
        parsers = {
            '.ipynb': self._parse_notebook,
            '.md': self._parse_markdown,
            '.py': self._parse_python
        }
        
        if file_ext not in parsers:
            msg = f"Error: Unsupported file type: {file_ext}. Supported types are: .ipynb, .md, .py"
            logging.error(msg)
            raise ValueError(msg)
            
        logging.info(f"Using parser: {parsers[file_ext].__name__}")
        return parsers[file_ext](file_path)

    def _parse_notebook(self, file_path: str) -> ParsedContent:
        logging.info(f"Parsing notebook file: {file_path}")
        try:
            notebook = nbformat.read(file_path, as_version=4)
        except Exception as e:
            msg = f"Error parsing notebook file: {file_path}. Details: {e}"
            logging.exception(msg)
            raise ValueError(msg)
        
        main_content_parts = []
        code_segments = []
        topics = set()
        complexity_indicators = set()
        
        for idx, cell in enumerate(notebook.cells):
            location = Location(
                section=f"Cell {idx + 1}",
                line_number=idx,
                context=f"Notebook cell {idx + 1}"
            )
            
            if cell.cell_type == 'markdown':
                main_content_parts.append(cell.source)
                # Extract topics from headers
                topics.update(re.findall(r'^#+ (.+)$', cell.source, re.MULTILINE))
                
            elif cell.cell_type == 'code':
                output_text = ""
                if hasattr(cell, 'outputs') and cell.outputs:
                    output_text = self._extract_notebook_output(cell.outputs)
                
                code_segment = CodeSegment(
                    code=cell.source,
                    language='python',
                    output=output_text,
                    location=location,
                    explanation=self._extract_code_explanation(cell.source)
                )
                code_segments.append(code_segment)
                
                # Identify complexity indicators
                complexity_indicators.update(self._identify_complexity_indicators(cell.source))
        
        # Build content graph
        content_graph = self._build_content_graph(main_content_parts, code_segments)
        
        logging.info(f"Extracted {len(main_content_parts)} markdown cells and {len(code_segments)} code segments")
        return ParsedContent(
            main_content='\n\n'.join(main_content_parts),
            code_segments=code_segments,
            metadata=ContentMetadata(
                file_type='notebook',
                title=Path(file_path).stem,
                topics=list(topics),
                complexity_indicators=list(complexity_indicators),
                prerequisites=self._identify_prerequisites(code_segments)
            ),
            content_graph=content_graph
        )
    
    def _parse_markdown(self, file_path: str) -> ParsedContent:
        logging.info(f"Parsing markdown file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            msg = f"Error reading markdown file: {file_path}. Details: {e}"
            logging.exception(msg)
            raise ValueError(msg)
            
        html = markdown2.markdown(content, extras=['fenced-code-blocks'])
        
        main_content = self._clean_markdown_content(content)
        code_segments = self._extract_markdown_code_blocks(content)
        topics = self._extract_markdown_topics(content)
        
        content_graph = self._build_content_graph([main_content], code_segments)
        
        logging.info(f"Extracted {len(code_segments)} code segments and {len(topics)} topics")
        return ParsedContent(
            main_content=main_content,
            code_segments=code_segments,
            metadata=ContentMetadata(
                file_type='markdown',
                title=self._extract_markdown_title(content),
                topics=topics,
                complexity_indicators=self._identify_complexity_indicators(content),
                prerequisites=self._identify_prerequisites(code_segments)
            ),
            content_graph=content_graph
        )
    
    def _parse_python(self, file_path: str) -> ParsedContent:
        logging.info(f"Parsing python file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            msg = f"Error reading python file: {file_path}. Details: {e}"
            logging.exception(msg)
            raise ValueError(msg)
            
        try:
            tree = ast.parse(content)
        except Exception as e:
            msg = f"Error parsing python file: {file_path}. Details: {e}"
            logging.exception(msg)
            raise ValueError(msg)
        
        docstring = ast.get_docstring(tree) or ""
        main_content = [docstring]
        code_segments = []
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                loc = Location(
                    section=node.name,
                    line_number=node.lineno,
                    context=f"Definition of {node.name}"
                )
                
                node_docstring = ast.get_docstring(node) or ""
                main_content.append(node_docstring)
                
                code_segment = CodeSegment(
                    code=self._get_node_source(node, content),
                    language='python',
                    explanation=node_docstring,
                    location=loc,
                    dependencies=self._extract_dependencies(node)
                )
                code_segments.append(code_segment)
        
        logging.info(f"Extracted {len(code_segments)} code segments")
        return ParsedContent(
            main_content='\n\n'.join(filter(None, main_content)),
            code_segments=code_segments,
            metadata=ContentMetadata(
                file_type='python',
                title=Path(file_path).stem,
                topics=self._extract_python_topics(tree),
                complexity_indicators=self._identify_complexity_indicators(content),
                prerequisites=self._identify_prerequisites(code_segments)
            ),
            content_graph=content_graph
        )

    def _extract_notebook_output(self, outputs: List[Dict]) -> str:
        output_text = ""
        for output in outputs:
            if 'text' in output:
                output_text += output.text
            elif 'data' in output and 'text/plain' in output.data:
                output_text += output.data['text/plain']
        return output_text

    def _extract_code_explanation(self, code: str) -> str:
        comments = re.findall(r'#\s*(.*?)$', code, re.MULTILINE)
        return '\n'.join(comments)

    def _identify_complexity_indicators(self, content: str) -> List[str]:
        indicators = []
        if re.search(r'for\s+\w+\s+in\s+range', content):
            indicators.append("Looping with range")
        if re.search(r'try:\s*except', content):
            indicators.append("Exception handling")
        if re.search(r'lambda\s+', content):
            indicators.append("Lambda functions")
        return indicators

    def _identify_prerequisites(self, code_segments: List[CodeSegment]) -> List[str]:
        prerequisites = set()
        for segment in code_segments:
            for dep in segment.dependencies:
                prerequisites.add(dep)
        return list(prerequisites)

    def _build_content_graph(self, main_content: List[str], code_segments: List[CodeSegment]) -> ContentGraph:
        topic_hierarchy = {}
        code_dependencies = {}
        concept_relationships = {}
        return ContentGraph(
            topic_hierarchy=topic_hierarchy,
            code_dependencies=code_dependencies,
            concept_relationships=concept_relationships
        )

    def _clean_markdown_content(self, content: str) -> str:
        content = ' '.join(content.split())
        content = re.sub(r'#{1,6}\s+', '', content)
        content = re.sub(r'<[^>]+>', '', content)
        content = content.replace('\r\n', '\n')
        return content.strip()

    def _extract_markdown_code_blocks(self, content: str) -> List[CodeSegment]:
        code_segments = []
        code_pattern = r'```(\w+)?\n(.*?)```'
        matches = re.finditer(code_pattern, content, re.DOTALL)
        
        for idx, match in enumerate(matches):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            
            # Extract any output if present (assuming output follows the code block)
            output = ""
            output_match = re.search(r'```output\n(.*?)```', content[match.end():], re.DOTALL)
            if output_match:
                output = output_match.group(1).strip()
            
            # Extract any explanation from comments above the code block
            explanation = ""
            if match.start() > 0:
                explanation_match = re.search(r'(?:^|\n)((?:[^\n]*\n)*?)```', content[:match.start()], re.MULTILINE)
                if explanation_match:
                    explanation = explanation_match.group(1).strip()
            
            code_segments.append(CodeSegment(
                code=code,
                language=language,
                output=output if output else None,
                explanation=explanation if explanation else None,
                location=Location(
                    section=f"Code Block {idx + 1}",
                    line_number=content[:match.start()].count('\n') + 1,
                    context="Markdown code block"
                )
            ))
        return code_segments

    def _extract_markdown_topics(self, content: str) -> List[str]:
        return re.findall(r'^#+ (.+)$', content, re.MULTILINE)

    def _extract_markdown_title(self, content: str) -> Optional[str]:
        title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
        return title_match.group(1) if title_match else None

    def _get_node_source(self, node: ast.AST, source: str) -> str:
        return ast.get_source_segment(source, node) or ""

    def _extract_dependencies(self, node: ast.AST) -> List[str]:
        dependencies = []
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for name in child.names:
                    dependencies.append(name.name)
            elif isinstance(child, ast.ImportFrom):
                dependencies.append(child.module)
        return dependencies

    def _extract_python_topics(self, tree: ast.AST) -> List[str]:
        topics = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if docstring:
                    topics.extend(re.findall(r'\b\w+\b', docstring))
        return topics
