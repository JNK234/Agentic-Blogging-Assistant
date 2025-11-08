# ABOUTME: This file defines the state management models for the blog refinement agent.
# ABOUTME: It includes state classes for title generation, SEO optimization, and social media content creation.
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from backend.agents.cost_tracking_state import CostTrackingMixin
from backend.models.generation_config import TitleGenerationConfig, SocialMediaConfig

class TitleOption(BaseModel):
    """Represents a single generated title/subtitle option."""
    title: str = Field(..., description="The main title suggestion.")
    subtitle: Optional[str] = Field(None, description="The corresponding subtitle suggestion.")
    reasoning: str = Field(..., description="Brief explanation of why this title/subtitle is suitable (e.g., SEO focus, catchiness).")

class RefinementResult(BaseModel):
    """Output model containing the refined blog content and metadata."""
    refined_draft: str = Field(..., description="The full blog content with the generated introduction and conclusion integrated.")
    summary: str = Field(..., description="A concise summary of the entire blog post.")
    title_options: List[TitleOption] = Field(..., description="A list of suggested title and subtitle options.")

class BlogRefinementState(CostTrackingMixin, BaseModel):
    """Represents the state managed by the BlogRefinementAgent's graph (if using LangGraph)."""
    original_draft: str
    introduction: Optional[str] = None # Added
    conclusion: Optional[str] = None # Added
    summary: Optional[str] = None
    title_options: Optional[List[TitleOption]] = None
    refined_draft: Optional[str] = None # Added to resolve AttributeError
    clarity_flow_suggestions: Optional[str] = Field(default=None, description="Suggestions for improving clarity and flow of the blog draft.")
    error: Optional[str] = None
    model: Optional[Any] = Field(default=None, repr=False)
    persona_service: Optional[Any] = Field(default=None, repr=False)
    project_id: Optional[str] = Field(default=None)

    # Configuration fields for generation control
    title_config: Optional[TitleGenerationConfig] = Field(
        default=None,
        description="Configuration for title and subtitle generation"
    )
    social_config: Optional[SocialMediaConfig] = Field(
        default=None,
        description="Configuration for social media post generation"
    )

    # SQL persistence (optional)
    sql_project_manager: Optional[Any] = Field(default=None, description="SQL project manager for milestone persistence")

    def __init__(self, **data):
        super().__init__(**data)
        self.current_agent_name = "BlogRefinementAgent"
        self.current_stage = data.get("current_stage", "refinement")
        if not self.project_id:
            self.project_id = data.get("project_id")
        self.ensure_cost_aggregator(project_id=self.project_id)
        if self.cost_aggregator and self.project_id and not self.cost_aggregator.current_workflow.get("start_time"):
            self.cost_aggregator.start_workflow(project_id=self.project_id)
