from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
#from root.backend.utils.file_parser import ParsedContent
from root.backend.services.vector_store_service import VectorStoreService
from dataclasses import asdict
import json

class ContentAnalysis(BaseModel):
    main_topics: List[str]
    technical_concepts: List[str]
    complexity_indicators: List[str]
    learning_objectives: List[str]

class DifficultyLevel(BaseModel):
    level: str = Field(description="Difficulty level (Beginner/Intermediate/Advanced)")
    reasoning: str = Field(description="Explanation for the chosen level")

class Prerequisites(BaseModel):
    required_knowledge: List[str]
    recommended_tools: List[str]
    setup_instructions: Optional[List[str]] = None

class OutlineSection(BaseModel):
    title: str
    subsections: List[str]
    learning_goals: List[str]
    estimated_time: Optional[str] = None

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

    def to_json(self) -> str:
        """Convert the FinalOutline instance to a JSON string."""
        return json.dumps(asdict(self), indent=2)

class OutlineState(BaseModel):
    # Input state
    notebook_content: Optional[Any] = Field(description="Parsed notebook content")
    markdown_content: Optional[Any] = Field(description="Parsed markdown content")
    model: Any = Field(description="LLM model instance")

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

    # model_config = {"arbitrary_types_allowed": True}
