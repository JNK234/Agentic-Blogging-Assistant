# ABOUTME: State modifications for cost tracking in LangGraph agents
# ABOUTME: Provides base class and utilities for tracking costs in agent states

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from root.backend.services.cost_aggregator import CostAggregator

class CostTrackingMixin(BaseModel):
    """Mixin to add cost tracking capabilities to any LangGraph state"""

    # Cost tracking fields
    cost_aggregator: Optional[CostAggregator] = Field(default=None, exclude=True)
    current_agent_name: str = Field(default="unknown")
    current_node_name: str = Field(default="unknown")
    current_iteration: Optional[int] = Field(default=None)
    current_section_index: Optional[int] = Field(default=None)
    current_stage: str = Field(default="workflow")
    project_id: Optional[str] = Field(default=None)

    # Cost summary (updated after each node)
    cost_summary: Dict[str, Any] = Field(default_factory=dict)

    def get_tracking_context(self) -> Dict[str, Any]:
        """Get the current tracking context for LLM calls"""
        return {
            "agent_name": self.current_agent_name,
            "node_name": self.current_node_name,
            "iteration": self.current_iteration,
            "section_index": self.current_section_index,
            "project_id": self.project_id,
            "stage": self.current_stage
        }

    def update_cost_summary(self):
        """Update the cost summary from the aggregator"""
        if self.cost_aggregator:
            self.cost_summary = self.cost_aggregator.get_workflow_summary()

    def get_node_cost(self, node_name: str) -> float:
        """Get the cost for a specific node"""
        if self.cost_aggregator:
            node_key = f"{self.current_agent_name}.{node_name}"
            return self.cost_aggregator.costs_by_node.get(node_key, {}).get("total_cost", 0)
        return 0

    def get_total_cost(self) -> float:
        """Get the total cost so far"""
        if self.cost_aggregator:
            return self.cost_aggregator.total_cost
        return 0

    def ensure_cost_aggregator(self, project_id: Optional[str] = None) -> None:
        """Ensure an aggregator exists and is associated with a project."""
        if not self.cost_aggregator:
            self.cost_aggregator = CostAggregator()
            resolved_project_id = project_id or getattr(self, 'project_id', None) or getattr(self, 'project_name', None) or 'unknown'
            self.project_id = resolved_project_id
            self.cost_aggregator.start_workflow(project_id=resolved_project_id)
        elif project_id and not self.project_id:
            self.project_id = project_id

    class Config:
        arbitrary_types_allowed = True
