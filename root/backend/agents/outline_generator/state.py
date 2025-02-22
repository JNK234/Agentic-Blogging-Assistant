from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from root.backend.utils.file_parser import ParsedContent
from root.backend.services.vector_store_service import VectorStoreService

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

class OutlineState(BaseModel):
    # Input state
    notebook_content: ParsedContent = Field(description="Parsed notebook content")
    markdown_content: ParsedContent = Field(description="Parsed markdown content")
    model: Any = Field(description="LLM model instance")
    vector_store: VectorStoreService = Field(default_factory=VectorStoreService)

    # Intermediate states
    analysis_result: Optional[ContentAnalysis] = None
    difficulty_level: Optional[str] = None
    prerequisites: Optional[Prerequisites] = None
    outline_structure: Optional[OutlineStructure] = None
    content_hash: str = Field(default="")
    cached_outline: Optional[str] = None
    content_mappings: Dict[str, Dict[str, List[str]]] = Field(
        default_factory=dict,
        description="Maps outline sections to relevant content chunks"
    )

    # Final state
    final_outline: Optional[str] = None

    # Metadata
    status: Dict[str, str] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}
