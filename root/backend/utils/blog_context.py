"""
ABOUTME: Blog context utilities for narrative context extraction and length management
ABOUTME: Pure functions for calculating blog flow, section lengths, and content priorities
"""
from typing import Dict, List
import re

def calculate_content_length(text: str) -> int:
    """
    Calculate the word count of the given text.
    
    Args:
        text: The text to count words for
        
    Returns:
        Number of words in the text
    """
    if not text or not text.strip():
        return 0
    
    # Remove extra whitespace and split by whitespace
    words = text.strip().split()
    return len(words)

def extract_blog_narrative_context(state) -> str:
    """
    Extract rich narrative context from the current blog state.
    
    Args:
        state: BlogDraftState object
        
    Returns:
        Formatted string with blog progression context
    """
    try:
        # Get basic blog information
        blog_title = getattr(state.outline, 'title', 'Untitled Blog')
        total_sections = len(getattr(state.outline, 'sections', []))
        current_position = state.current_section_index + 1
        
        # Get completed sections info
        completed_titles = [section.title for section in state.sections]
        
        # Get upcoming sections
        upcoming_sections = []
        if hasattr(state.outline, 'sections') and state.outline.sections:
            remaining_start = state.current_section_index
            remaining_end = min(remaining_start + 3, len(state.outline.sections))
            upcoming_sections = [
                state.outline.sections[i].title 
                for i in range(remaining_start, remaining_end)
            ]
        
        # Build context string
        context_parts = [
            f"Blog Title: {blog_title}",
            f"Current Position: Section {current_position} of {total_sections}",
        ]
        
        if completed_titles:
            context_parts.append(f"Completed Sections: {', '.join(completed_titles)}")
        
        if upcoming_sections:
            context_parts.append(f"Upcoming Sections: {', '.join(upcoming_sections)}")
        
        # Add blog introduction if available
        if hasattr(state.outline, 'introduction') and state.outline.introduction:
            intro_preview = state.outline.introduction[:200]
            if len(state.outline.introduction) > 200:
                intro_preview += "..."
            context_parts.append(f"Blog Introduction: {intro_preview}")
        
        return "\n".join(context_parts)
        
    except Exception as e:
        # Graceful fallback for any errors
        return f"Blog Context: Section {getattr(state, 'current_section_index', 0) + 1}"

def calculate_section_length_targets(outline, target_total: int) -> Dict[str, int]:
    """
    Calculate target lengths for each section based on outline structure.
    
    Args:
        outline: FinalOutline object with sections
        target_total: Target total blog length in words
        
    Returns:
        Dictionary mapping section titles to target word counts
    """
    if not outline or not hasattr(outline, 'sections') or not outline.sections:
        return {}
    
    sections = outline.sections
    total_sections = len(sections)
    
    if total_sections == 0:
        return {}
    
    # Reserve space for introduction and conclusion
    intro_length = 200  # Estimated introduction length
    conclusion_length = 150  # Estimated conclusion length
    available_for_sections = max(target_total - intro_length - conclusion_length, target_total * 0.8)
    
    # Calculate base length per section
    base_length_per_section = int(available_for_sections / total_sections)
    
    # Adjust based on section complexity (number of subsections)
    section_targets = {}
    total_complexity = sum(len(getattr(section, 'subsections', [])) for section in sections)
    
    for section in sections:
        # Base allocation
        target_length = base_length_per_section
        
        # Adjust based on subsection count (more subsections = longer section)
        subsection_count = len(getattr(section, 'subsections', []))
        if total_complexity > 0:
            complexity_factor = subsection_count / total_complexity
            adjustment = int(available_for_sections * 0.2 * complexity_factor)
            target_length += adjustment
        
        # Ensure minimum and maximum bounds
        target_length = max(target_length, 300)  # Minimum section length
        target_length = min(target_length, int(target_total * 0.4))  # Max 40% of total blog
        
        section_targets[section.title] = target_length
    
    return section_targets

def get_length_priority(current_length: int, target_length: int, remaining_budget: int) -> str:
    """
    Determine the length priority for the current section generation.
    
    Args:
        current_length: Current blog length in words
        target_length: Target length for current section
        remaining_budget: Remaining word budget for all sections
        
    Returns:
        Priority string: "expand", "maintain", or "compress"
    """
    if remaining_budget <= 0:
        return "compress"
    
    # Calculate how much over/under we are relative to target
    if target_length <= 0:
        return "maintain"
    
    # If we have plenty of budget left, we can expand
    budget_ratio = remaining_budget / max(target_length, 1)
    
    if budget_ratio >= 1.5:
        return "expand"
    elif budget_ratio >= 0.8:
        return "maintain"
    else:
        return "compress"