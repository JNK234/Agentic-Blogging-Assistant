"""
Utility functions for the Blog Draft Generator.
"""
import logging
import re
import json
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from root.backend.services.vector_store_service import VectorStoreService
from root.backend.agents.blog_draft_generator.state import ContentReference, CodeExample

logging.basicConfig(level=logging.INFO)

def build_hierarchical_structure(section_headers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Builds a hierarchical representation of document structure from headers.
    
    Args:
        section_headers: List of section header dictionaries with level and text
        
    Returns:
        List of dictionaries representing document hierarchy
    """
    hierarchy = []
    header_stack = []
    
    # Sort headers by their position in the document
    sorted_headers = sorted(section_headers, key=lambda h: h.get('position', 0))
    
    for header in sorted_headers:
        level = header.get('level', 1)
        
        # Pop stack until we find a parent or empty the stack
        while header_stack and header_stack[-1]['level'] >= level:
            header_stack.pop()
        
        # Create node with parent reference
        node = {
            'text': header.get('text', ''),
            'level': level,
            'parent': header_stack[-1]['text'] if header_stack else None,
            'children': []
        }
        
        # Add as child to parent if exists
        if header_stack:
            header_stack[-1]['children'].append(node['text'])
        
        # Add to hierarchy and stack
        hierarchy.append(node)
        header_stack.append(node)
    
    return hierarchy

def build_contextual_query(section_title: str, learning_goals: List[str], 
                         relevant_headers: List[Dict[str, Any]], 
                         document_structure: List[Dict[str, Any]]) -> str:
    """
    Builds a rich contextual query incorporating structural information.
    
    Args:
        section_title: Title of the section
        learning_goals: List of learning goals
        relevant_headers: List of relevant headers with similarity scores
        document_structure: Hierarchical document structure
        
    Returns:
        Enhanced query string incorporating structural context
    """
    # Start with section title and learning goals
    query_components = [section_title]
    query_components.extend(learning_goals)
    
    # Add relevant headers with weighting based on similarity
    for header in relevant_headers[:3]:  # Top 3 most relevant headers
        query_components.append(f"{header['text']}")
    
    # Add structural context from document hierarchy
    for header in relevant_headers[:2]:  # Top 2 headers
        # Find this header in document structure
        for node in document_structure:
            if node['text'] == header['text']:
                # Add parent context if exists
                if node['parent']:
                    query_components.append(f"Related to {node['parent']}")
                
                # Add children context if exists
                for child in node['children'][:2]:  # Top 2 children
                    query_components.append(f"Includes {child}")
    
    # Combine into a weighted query string
    return " ".join(query_components)

def process_search_results(search_results: List[Dict[str, Any]], 
                         relevant_headers: List[Dict[str, Any]], 
                         document_structure: List[Dict[str, Any]]) -> List[ContentReference]:
    """
    Processes search results with structural awareness.
    
    Args:
        search_results: List of search results from vector store
        relevant_headers: List of relevant headers with similarity scores
        document_structure: Hierarchical document structure
        
    Returns:
        List of ContentReference objects with structural context
    """
    references = []
    
    # Create a mapping of header text to its structural information
    header_structure = {node['text']: node for node in document_structure}
    
    for result in search_results:
        # Calculate structural relevance boost
        structural_boost = 0.0
        structural_context = {}
        
        # Check if result content contains or relates to relevant headers
        for header in relevant_headers:
            if header['text'] in result['content']:
                # Boost based on header similarity
                structural_boost += header.get('similarity', 0.5) * 0.2
                
                # Add header to structural context
                if header['text'] in header_structure:
                    node = header_structure[header['text']]
                    structural_context[header['text']] = {
                        'level': node['level'],
                        'parent': node['parent'],
                        'children': node['children']
                    }
                    
                    # Additional boost if header has parent-child relationships
                    if node['parent'] and node['parent'] in result['content']:
                        structural_boost += 0.1
                        
                    for child in node['children']:
                        if child in result['content']:
                            structural_boost += 0.05
        
        # Create ContentReference with structural awareness
        reference = ContentReference(
            content=result['content'],
            source_type=result['metadata'].get('source_type', 'markdown'),
            relevance_score=min(1.0, result['relevance'] + structural_boost),
            category=determine_content_category(result, relevant_headers),
            source_location=result['metadata'].get('source_location', ''),
            structural_context=structural_context if structural_context else None
        )
        
        references.append(reference)
    
    # Sort by adjusted relevance
    references.sort(key=lambda x: x.relevance_score, reverse=True)
    return references

def determine_content_category(result: Dict[str, Any], 
                             relevant_headers: List[Dict[str, Any]]) -> str:
    """
    Determines the category of content based on its characteristics and context.
    
    Args:
        result: Search result dictionary
        relevant_headers: List of relevant headers
        
    Returns:
        Category string
    """
    content = result['content'].lower()
    
    # Check for code examples
    if '```' in content or 'example:' in content:
        return 'example'
    
    # Check for implementation details
    if any(term in content for term in ['implementation', 'setup', 'configure', 'install']):
        return 'implementation'
    
    # Check for best practices
    if any(term in content for term in ['best practice', 'recommended', 'tip', 'important']):
        return 'best_practice'
    
    # Default to concept
    return 'concept'

def extract_code_blocks(content: str) -> List[Dict[str, str]]:
    """
    Extracts code blocks from markdown content.
    
    Args:
        content: Markdown content with code blocks
        
    Returns:
        List of dictionaries with language and code
    """
    code_blocks = []
    matches = re.findall(r'```(\w+)?\n(.*?)```', content, re.DOTALL)
    
    for language, code in matches:
        language = language or "text"
        code_blocks.append({
            "language": language,
            "code": code.strip()
        })
    
    return code_blocks

def format_content_references(references: List[ContentReference]) -> str:
    """
    Formats content references for use in prompts.
    
    Args:
        references: List of ContentReference objects
        
    Returns:
        Formatted string of references
    """
    if not references:
        return "No relevant content available."
    
    formatted = []
    for ref in references:
        formatted.append(
            f"CONTENT ({ref.category}, Relevance: {ref.relevance_score}):\n{ref.content}"
        )
    
    return "\n\n".join(formatted)

def extract_section_metrics(section_content: str) -> Dict[str, float]:
    """
    Extracts metrics from a section's content.
    
    Args:
        section_content: The content of the section
        
    Returns:
        Dictionary of metrics
    """
    metrics = {
        "word_count": len(section_content.split()),
        "code_block_count": len(re.findall(r'```\w*\n', section_content)),
        "heading_count": len(re.findall(r'^#{2,}\s+.+$', section_content, re.MULTILINE)),
        "list_item_count": len(re.findall(r'^[\s]*[-*]\s+.+$', section_content, re.MULTILINE))
    }
    
    return metrics

def store_blog_in_vector_store(
    blog_content: str, 
    title: str, 
    sections: List[Dict], 
    project_name: Optional[str] = None
) -> Optional[str]:
    """
    Stores the generated blog in the vector store for future reference.
    
    Args:
        blog_content: The full blog content
        title: The blog title
        sections: List of section dictionaries
        project_name: Optional project name
        
    Returns:
        Content hash if successful, None otherwise
    """
    try:
        vector_store = VectorStoreService()
        
        # Create chunks from sections
        chunks = []
        metadata = []
        
        # Add title and metadata as first chunk
        chunks.append(f"# {title}\n\nBlog post generated by Agentic Blogging Assistant")
        
        # Create metadata for the first chunk
        base_metadata = {
            "content_type": "blog",
            "title": title,
            "project_name": project_name,
            "generated_at": datetime.now().isoformat(),
            "file_type": "markdown"
        }
        
        metadata.append(base_metadata)
        
        # Add each section as a chunk
        for i, section in enumerate(sections):
            chunks.append(f"## {section['title']}\n\n{section['content']}")
            
            section_metadata = base_metadata.copy()
            section_metadata.update({
                "section_title": section["title"],
                "section_index": i
            })
            
            metadata.append(section_metadata)
        
        # Generate content hash
        content_hash = vector_store.compute_content_hash(blog_content, title)
        
        # Store in vector store
        vector_store.store_content_chunks(
            chunks=chunks,
            metadata=metadata,
            content_hash=content_hash
        )
        
        logging.info(f"Blog '{title}' stored in vector store with hash {content_hash}")
        return content_hash
        
    except Exception as e:
        logging.error(f"Error storing blog in vector store: {e}")
        return None

def parse_json_safely(json_str: str, default_value: Any = None) -> Any:
    """
    Safely parses JSON, stripping optional markdown fences, with fallback to default value.

    Args:
        json_str: JSON string to parse, potentially wrapped in ```json ... ``` or ``` ... ```
        default_value: Default value to return if parsing fails

    Returns:
        Parsed JSON or default value
    """
    # Regex to find JSON content within ```json ... ``` or ``` ... ```
    # Handles potential leading/trailing whitespace within the fences
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', json_str, re.DOTALL)
    if match:
        # If fences are found, extract the content within them
        content_to_parse = match.group(1).strip()
        logging.info("Stripped markdown fences from JSON string.")
    else:
        # If no fences, assume the whole string is the JSON content
        content_to_parse = json_str.strip()

    # Handle empty string after stripping
    if not content_to_parse:
        logging.warning("JSON content is empty after stripping fences/whitespace. Returning default value.")
        return default_value

    try:
        # Attempt to parse the extracted or original content
        return json.loads(content_to_parse)
    except json.JSONDecodeError as e:
        # Log the error and the problematic content (truncated) for debugging
        logging.warning(f"Failed to parse JSON: {e}. Content attempted: '{content_to_parse[:100]}...' Returning default value.")
        return default_value

def format_code_examples(code_examples: List[CodeExample]) -> str:
    """
    Formats code examples for inclusion in the blog.
    
    Args:
        code_examples: List of CodeExample objects
        
    Returns:
        Formatted string of code examples with explanations
    """
    if not code_examples:
        return ""
    
    formatted = []
    for example in code_examples:
        formatted.append(
            f"### {example.description}\n\n"
            f"{example.explanation}\n\n"
            f"```{example.language}\n{example.code}\n```"
        )
        
        if example.output:
            formatted.append(f"Output:\n```\n{example.output}\n```")
    
    return "\n\n".join(formatted)

def generate_table_of_contents(sections: List[Dict]) -> str:
    """
    Generates a table of contents from section information.
    
    Args:
        sections: List of section dictionaries with titles
        
    Returns:
        Markdown formatted table of contents
    """
    toc = ["## Table of Contents"]
    
    for i, section in enumerate(sections):
        toc.append(f"{i+1}. [{section['title']}](#section-{i+1})")
    
    return "\n".join(toc)
