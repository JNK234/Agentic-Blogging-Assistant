# -*- coding: utf-8 -*-
"""
Pydantic models for the Blog Refinement Agent state.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class TitleOption(BaseModel):
    """Represents a single generated title/subtitle option."""
    title: str = Field(..., description="The main title suggestion.")
    subtitle: str = Field(..., description="The corresponding subtitle suggestion.")
    reasoning: str = Field(..., description="Brief explanation of why this title/subtitle is suitable (e.g., SEO focus, catchiness).")

class RefinementResult(BaseModel):
    """Output model containing the refined blog content and metadata."""
    refined_draft: str = Field(..., description="The full blog content with the generated introduction and conclusion integrated.")
    summary: str = Field(..., description="A concise summary of the entire blog post.")
    title_options: List[TitleOption] = Field(..., description="A list of suggested title and subtitle options.")

class BlogRefinementState(BaseModel):
    """Represents the state managed by the BlogRefinementAgent's graph (if using LangGraph)."""
    original_draft: str
    refined_draft: Optional[str] = None
    introduction: Optional[str] = None # Added missing field
    conclusion: Optional[str] = None # Added missing field
    summary: Optional[str] = None
    title_options: Optional[List[TitleOption]] = None
    error: Optional[str] = None
    # Add any other intermediate states if needed for a graph-based approach
