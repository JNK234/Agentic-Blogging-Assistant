# ABOUTME: Workflow types and enumerations used across the blogging assistant application.
# ABOUTME: Defines workflow stages, states, and other shared types to avoid circular imports.

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

class WorkflowStage(Enum):
    """Workflow stages for the blogging pipeline."""
    PROJECT_SETUP = "project_setup"
    FILE_UPLOAD = "file_upload" 
    CONTENT_PROCESSING = "content_processing"
    OUTLINE_GENERATION = "outline_generation"
    BLOG_DRAFTING = "blog_drafting"
    BLOG_REFINEMENT = "blog_refinement"
    SOCIAL_CONTENT = "social_content"
    EXPORT = "export"
    COMPLETE = "complete"

class ContentType(Enum):
    """Types of content that can be processed."""
    JUPYTER_NOTEBOOK = "jupyter_notebook"
    MARKDOWN = "markdown"
    PYTHON = "python"
    TEXT = "text"

class ExportFormat(Enum):
    """Available export formats."""
    MARKDOWN = "markdown"
    HTML = "html" 
    PDF = "pdf"
    DOCX = "docx"
    JSON = "json"

@dataclass
class ProjectConfig:
    """Project configuration data structure."""
    name: str
    model_name: str = "gemini"
    writing_style: str = "professional"
    persona: str = ""
    id: Optional[str] = None
    created_at: Optional[str] = None
    resumed: bool = False
    resumed_at: Optional[str] = None

@dataclass
class WorkflowProgress:
    """Workflow progress tracking."""
    current_stage: WorkflowStage
    completed_stages: List[WorkflowStage]
    total_stages: int
    progress_percentage: float
    next_stage: Optional[WorkflowStage] = None
    available_stages: List[WorkflowStage] = None

@dataclass
class ContentStats:
    """Content statistics."""
    word_count: int = 0
    character_count: int = 0
    paragraph_count: int = 0
    estimated_read_time: int = 0
    sections_count: int = 0

@dataclass
class ProcessingResults:
    """File processing results."""
    upload_result: Dict[str, Any]
    process_result: Dict[str, Any]
    project_id: Optional[str] = None
    file_hashes: Dict[str, str] = None
    
    def __post_init__(self):
        if self.file_hashes is None:
            self.file_hashes = {}

@dataclass
class WorkflowEvent:
    """Workflow event for history tracking."""
    type: str
    data: Dict[str, Any]
    timestamp: str
    session_id: str