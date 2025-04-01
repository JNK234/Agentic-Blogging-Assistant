from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any
#from root.backend.utils.file_parser import ParsedContent
from root.backend.parsers.base import ContentStructure # Added import
from root.backend.services.vector_store_service import VectorStoreService
from root.backend.utils.serialization import to_json, model_to_dict, serialize_object
from dataclasses import asdict
import json

class ContentAnalysis(BaseModel):
    main_topics: List[str]
    technical_concepts: List[str]
    complexity_indicators: List[str]
    learning_objectives: List[str]
    section_structure: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Hierarchical section structure from source content")

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

class OutlineState(BaseModel):
    # Input state
    notebook_content: Optional[ContentStructure] = Field(description="Parsed notebook content") # Updated type hint
    markdown_content: Optional[ContentStructure] = Field(description="Parsed markdown content") # Updated type hint
    model: Any = Field(description="LLM model instance")
    user_guidelines: Optional[str] = Field(default=None, description="Optional user-provided guidelines for outline generation")

    # Intermediate states
    analysis_result: Optional[ContentAnalysis] = None
    difficulty_level: Optional[DifficultyLevel] = None
    prerequisites: Optional[Prerequisites] = None
    outline_structure: Optional[OutlineStructure] = None

    # Final state
    final_outline: Optional[FinalOutline] = None

    # # Metadata
    # status: Dict[str, str] = Field(default_factory=dict)
    # errors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True) # Added config
