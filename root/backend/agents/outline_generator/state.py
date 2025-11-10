# ABOUTME: This file defines the state management models for the outline generation agent.
# ABOUTME: It includes state classes for content analysis, difficulty assessment, and outline structure creation.
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
from backend.parsers.base import ContentStructure
from backend.services.vector_store_service import VectorStoreService
from backend.utils.serialization import to_json, model_to_dict, serialize_object
from dataclasses import asdict
import json
from backend.agents.cost_tracking_state import CostTrackingMixin

class ContentAnalysis(BaseModel):
    main_topics: List[str]
    technical_concepts: List[str]
    complexity_indicators: List[str]
    learning_objectives: List[str]
    section_structure: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Hierarchical section structure from source content")
    has_actual_code: bool = Field(default=False, description="Whether content contains actual implementable code vs theoretical concepts")
    content_type: str = Field(default="theoretical", description="Content classification: theoretical, practical, or mixed")
    estimated_content_density: str = Field(default="medium", description="Content density assessment: low, medium, high, very_high")
    suggested_blog_length: int = Field(default=1500, description="AI-recommended optimal blog length in words")
    length_reasoning: str = Field(default="", description="Explanation for the suggested blog length")

class DifficultyLevel(BaseModel):
    level: str = Field(description="Difficulty level (Beginner/Intermediate/Advanced)")
    reasoning: str = Field(description="Explanation for the chosen level")

class Prerequisites(BaseModel):
    required_knowledge: List[str]
    recommended_tools: List[str]
    setup_instructions: Optional[List[str]] = []

class OutlineSection(BaseModel):
    title: str
    subsections: List[str]
    learning_goals: List[str]
    estimated_time: Optional[str] = None
    include_code: bool = Field(default=False, description="Whether code examples are recommended")
    max_subpoints: Optional[int] = Field(default=4, description="Suggested max subsections")
    max_code_examples: Optional[int] = Field(default=1, description="Suggested max code examples if code included")

class OutlineStructure(BaseModel):
    title: str
    sections: List[OutlineSection]
    introduction: str
    conclusion: str

class FinalOutline(BaseModel):
    title: str
    difficulty_level: str
    prerequisites: Prerequisites
    introduction: str
    sections: List[OutlineSection]
    conclusion: str

    # def to_json(self) -> str:
    #     """Convert the FinalOutline instance to a JSON string."""
    #     return to_json(self, indent=2)
        
    # def model_dump(self):
    #     """Make the object JSON serializable by returning a dictionary representation."""
    #     return model_to_dict(self)

class OutlineState(CostTrackingMixin, BaseModel):
    # Input state
    notebook_content: Optional[ContentStructure] = Field(default=None, description="Parsed notebook content")
    markdown_content: Optional[ContentStructure] = Field(default=None, description="Parsed markdown content")
    model: Any = Field(description="LLM model instance")
    user_guidelines: Optional[str] = Field(default=None, description="Optional user-provided guidelines for outline generation")
    length_preference: Optional[str] = Field(default=None, description="User's preferred blog length category")
    custom_length: Optional[int] = Field(default=None, description="Custom target word count if specified")
    writing_style: Optional[str] = Field(default=None, description="User's preferred writing style")
    persona: str = Field(default="neuraforge", description="Selected persona for content generation")

    # Intermediate states
    analysis_result: Optional[ContentAnalysis] = None
    difficulty_level: Optional[DifficultyLevel] = None
    prerequisites: Optional[Prerequisites] = None
    outline_structure: Optional[OutlineStructure] = None

    # Final state
    final_outline: Optional[FinalOutline] = None

    # Project metadata for cost tracking
    project_name: Optional[str] = Field(default=None)

    # SQL persistence (optional)
    sql_project_manager: Optional[Any] = Field(default=None, description="SQL project manager for milestone persistence")

    def __init__(self, **data):
        super().__init__(**data)
        self.current_agent_name = "OutlineGeneratorAgent"
        self.current_stage = data.get("current_stage", "outline_generation")
        if not self.project_id:
            self.project_id = data.get("project_id") or self.project_name
        self.ensure_cost_aggregator(project_id=self.project_id)
        if self.cost_aggregator and self.project_id:
            # Ensure workflow started only once
            if not self.cost_aggregator.current_workflow.get("start_time"):
                self.cost_aggregator.start_workflow(project_id=self.project_id)

    # # Metadata
    # status: Dict[str, str] = Field(default_factory=dict)
    # errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True) # Added config
