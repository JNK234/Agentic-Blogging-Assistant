# ABOUTME: This file defines the state management models for the blog draft generation agent.
# ABOUTME: It includes state classes for tracking section generation, quality validation, and iteration progress.
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Set
from backend.parsers import ContentStructure
from backend.agents.outline_generator.state import FinalOutline
from backend.agents.cost_tracking_state import CostTrackingMixin

class CodeExample(BaseModel):
    """Represents a code example in a blog section."""
    code: str
    language: str
    description: str
    explanation: Optional[str] = None
    output: Optional[str] = None
    source_location: Optional[str] = None

class SectionFeedback(BaseModel):
    """Feedback for a blog section."""
    content: str
    source: str  # "auto" or "user"
    timestamp: str
    addressed: bool = False

class SectionVersion(BaseModel):
    """Represents a version of a blog section."""
    content: str
    version_number: int
    timestamp: str
    changes: Optional[str] = None  # Description of changes from previous version

class ImagePlaceholder(BaseModel):
    """Represents an image placeholder suggestion for enhanced content visualization."""
    type: str = Field(description="Type of image: diagram, screenshot, chart, illustration, etc.")
    description: str = Field(description="Detailed description of what the image should show")
    alt_text: str = Field(description="Accessibility description for screen readers")
    placement: str = Field(description="Where to place: section_start, after_concept, section_end, etc.")
    purpose: str = Field(description="How this image enhances content understanding")
    section_context: Optional[str] = Field(default=None, description="Which concept/paragraph it relates to")
    source_reference: Optional[str] = Field(default=None, description="Reference to source material if applicable")

class DraftSection(BaseModel):
    """Represents a section in the blog draft."""
    title: str
    content: str
    feedback: List[SectionFeedback] = Field(default_factory=list)
    versions: List[SectionVersion] = Field(default_factory=list)
    current_version: int = 1
    status: str = "draft"  # "draft", "review", "approved"
    code_examples: List[CodeExample] = Field(default_factory=list)
    key_concepts: List[str] = Field(default_factory=list)
    technical_terms: List[str] = Field(default_factory=list)

    # ENHANCED: Comprehensive quality metrics
    quality_metrics: Dict[str, float] = Field(default_factory=dict)  # e.g., {"clarity": 0.8, "technical_depth": 0.7}

    # NEW: Detailed scoring breakdowns
    content_quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    persona_compliance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    structural_compliance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # NEW: Issue tracking
    content_issues: List[str] = Field(default_factory=list)
    persona_violations: List[str] = Field(default_factory=list)
    structural_violations: List[str] = Field(default_factory=list)

    # Existing image placeholders field
    image_placeholders: List[ImagePlaceholder] = Field(default_factory=list, description="Suggested image placeholders for visual enhancement")

class ContentReference(BaseModel):
    """Reference to content from source materials."""
    content: str
    source_type: str  # "notebook", "markdown", "code"
    relevance_score: float
    category: str  # "concept", "example", "implementation", "best_practice"
    source_location: Optional[str] = None
    structural_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Stores header relationships and context from original document structure"
    )

class BlogDraftState(CostTrackingMixin, BaseModel):
    """State for the blog draft generation process."""
    # Input state
    project_name: str = Field(description="Name of the project for context filtering") # Added project_name
    outline: FinalOutline
    notebook_content: ContentStructure = Field(description="Parsed notebook content")
    markdown_content: ContentStructure = Field(description="Parsed markdown content")
    current_section_index: int = 0
    model: Any = Field(description="LLM model instance")
    persona: str = Field(default="neuraforge", description="Selected persona for content generation")

    # Content state
    sections: List[DraftSection] = Field(default_factory=list)
    current_section: Optional[DraftSection] = None
    completed_sections: Set[int] = Field(default_factory=set)
    
    # Generation tracking
    generation_stage: str = "planning"  # "planning", "drafting", "enhancing", "finalizing"
    iteration_count: int = 0
    max_iterations: int = 3
    quality_threshold: float = 0.8  # Added quality threshold

    # NEW: Quality dimension weights
    quality_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            'content': 0.4,    # 40% weight on content quality
            'persona': 0.3,    # 30% weight on persona compliance
            'structure': 0.3   # 30% weight on structural compliance
        }
    )

    # NEW: Post type for structural rules
    post_type: str = Field(default="default", description="Type of blog post for structural rules")

    # Reference mapping
    content_mapping: Dict[str, List[ContentReference]] = Field(default_factory=dict)  # Maps sections to relevant content (Original RAG)

    # HyDE RAG specific fields
    hypothetical_document: Optional[str] = Field(default=None, description="Hypothetical document generated for HyDE retrieval")
    hyde_retrieved_context: Optional[List[Dict]] = Field(default=None, description="Context retrieved using HyDE")

    # Blog structure
    table_of_contents: List[Dict[str, str]] = Field(default_factory=list)
    transitions: Dict[str, str] = Field(default_factory=dict)  # Transitions between sections
    
    # Metadata
    status: Dict[str, str] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)  # Performance and quality metrics
    
    # Feedback Incorporation
    user_feedback_provided: bool = Field(default_factory=bool)
    
    # Length Management - Now dynamic based on content analysis
    target_total_length: int = Field(default=1500, description="Target total blog length in words - dynamically calculated")
    section_length_targets: Dict[str, int] = Field(default_factory=dict, description="Target length for each section")
    current_total_length: int = Field(default=0, description="Current total blog length in words")
    remaining_length_budget: int = Field(default=1500, description="Remaining length budget for upcoming sections")

    project_id: Optional[str] = Field(default=None)

    # SQL persistence (optional)
    sql_project_manager: Optional[Any] = Field(default=None, description="SQL project manager for milestone and section persistence")

    def __init__(self, **data):
        super().__init__(**data)
        self.current_agent_name = "BlogDraftGeneratorAgent"
        self.current_stage = data.get("current_stage", "draft_generation")
        if not self.project_id:
            self.project_id = data.get("project_id") or self.project_name
        self.ensure_cost_aggregator(project_id=self.project_id)
        if self.cost_aggregator and self.project_id and not self.cost_aggregator.current_workflow.get("start_time"):
            self.cost_aggregator.start_workflow(project_id=self.project_id)
