"""
State management for content parsing.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from pathlib import Path
from backend.agents.cost_tracking_state import CostTrackingMixin

class ContentParsingState(CostTrackingMixin):
    # Input state
    file_path: str
    project_name: Optional[str] = None

    # Processing state
    validation_result: Optional[Dict[str, bool]] = None
    parsed_content: Optional[Any] = None
    content_chunks: Optional[List[str]] = None
    metadata: Optional[Dict] = None
    content_hash: Optional[str] = None
    chunk_metadata: Optional[List] = None

    # Error handling
    errors: List[str] = []

    model_config = {"arbitrary_types_allowed": True}
