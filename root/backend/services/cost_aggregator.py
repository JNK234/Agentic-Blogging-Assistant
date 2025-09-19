# ABOUTME: Cost aggregation service for tracking costs across LangGraph agents and nodes
# ABOUTME: Provides hierarchical cost tracking and real-time reporting

from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class CostAggregator:
    """
    Aggregates costs across multiple agents, nodes, and iterations in LangGraph workflows.
    Provides hierarchical cost tracking without requiring a database.
    """

    def __init__(self):
        """Initialize the cost aggregator"""
        # Hierarchical tracking
        self.costs_by_agent = defaultdict(lambda: {"total_cost": 0, "total_tokens": 0, "calls": 0})
        self.costs_by_node = defaultdict(lambda: {"total_cost": 0, "total_tokens": 0, "calls": 0})
        self.costs_by_iteration = defaultdict(lambda: {"total_cost": 0, "total_tokens": 0})
        self.costs_by_section = defaultdict(lambda: {"total_cost": 0, "total_tokens": 0})
        self.costs_by_stage = defaultdict(lambda: {"total_cost": 0, "total_tokens": 0, "calls": 0})

        # Overall tracking
        self.total_cost = 0.0
        self.total_tokens = 0
        self.total_calls = 0

        # Detailed call history
        self.call_history = []

        # Current workflow context
        self.current_workflow = {
            "project_id": None,
            "start_time": None,
            "agent_stack": []  # Track nested agent calls
        }

    def start_workflow(self, project_id: str):
        """Mark the start of a new workflow"""
        self.current_workflow = {
            "project_id": project_id,
            "start_time": datetime.utcnow(),
            "agent_stack": []
        }
        logger.info(f"Started cost tracking for project: {project_id}")

    def enter_agent(self, agent_name: str):
        """Track when entering an agent"""
        self.current_workflow["agent_stack"].append(agent_name)

    def exit_agent(self):
        """Track when exiting an agent"""
        if self.current_workflow["agent_stack"]:
            self.current_workflow["agent_stack"].pop()

    def record_cost(self, call_record: Dict[str, Any]):
        """
        Record a single LLM call cost

        Args:
            call_record: Dictionary containing cost information and context
        """
        # Extract key information
        cost = call_record.get("total_cost", 0)
        tokens = call_record.get("total_tokens", 0)
        agent_name = call_record.get("agent_name", "unknown")
        node_name = call_record.get("node_name", "unknown")
        iteration = call_record.get("iteration")
        section_index = call_record.get("section_index")
        stage = call_record.get("stage", "unknown")

        # Update aggregations
        self.total_cost += cost
        self.total_tokens += tokens
        self.total_calls += 1

        # Update by agent
        self.costs_by_agent[agent_name]["total_cost"] += cost
        self.costs_by_agent[agent_name]["total_tokens"] += tokens
        self.costs_by_agent[agent_name]["calls"] += 1

        # Update by stage
        self.costs_by_stage[stage]["total_cost"] += cost
        self.costs_by_stage[stage]["total_tokens"] += tokens
        self.costs_by_stage[stage]["calls"] += 1

        # Update by node
        node_key = f"{agent_name}.{node_name}"
        self.costs_by_node[node_key]["total_cost"] += cost
        self.costs_by_node[node_key]["total_tokens"] += tokens
        self.costs_by_node[node_key]["calls"] += 1

        # Update by iteration if applicable
        if iteration is not None:
            iter_key = f"{node_key}_iter_{iteration}"
            self.costs_by_iteration[iter_key]["total_cost"] += cost
            self.costs_by_iteration[iter_key]["total_tokens"] += tokens

        # Update by section if applicable
        if section_index is not None:
            section_key = f"section_{section_index}"
            self.costs_by_section[section_key]["total_cost"] += cost
            self.costs_by_section[section_key]["total_tokens"] += tokens

        # Add to history
        self.call_history.append({
            **call_record,
            "workflow_context": {
                "project_id": self.current_workflow.get("project_id"),
                "agent_stack": self.current_workflow["agent_stack"].copy()
            }
        })

        # Log significant costs
        if cost > 0.01:  # Log calls over 1 cent
            logger.warning(
                f"High-cost call: {agent_name}.{node_name} | "
                f"Tokens: {tokens} | Cost: ${cost:.4f}"
            )

    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary of current workflow costs"""
        summary = {
            "total_cost": round(self.total_cost, 6),
            "total_tokens": self.total_tokens,
            "total_calls": self.total_calls,
            "average_cost_per_call": round(self.total_cost / max(self.total_calls, 1), 6),

            # By agent breakdown
            "by_agent": {
                name: {
                    "cost": round(data["total_cost"], 6),
                    "tokens": data["total_tokens"],
                    "calls": data["calls"],
                    "percentage": round((data["total_cost"] / max(self.total_cost, 0.000001)) * 100, 2)
                }
                for name, data in self.costs_by_agent.items()
            },

            # By stage breakdown
            "by_stage": {
                name: {
                    "cost": round(data["total_cost"], 6),
                    "tokens": data["total_tokens"],
                    "calls": data["calls"],
                    "percentage": round((data["total_cost"] / max(self.total_cost, 0.000001)) * 100, 2)
                }
                for name, data in self.costs_by_stage.items()
            },

            # By node breakdown
            "by_node": {
                name: {
                    "cost": round(data["total_cost"], 6),
                    "tokens": data["total_tokens"],
                    "calls": data["calls"]
                }
                for name, data in self.costs_by_node.items()
            },

            # By section (for blog generation)
            "by_section": dict(self.costs_by_section) if self.costs_by_section else None,

            # Top expensive nodes
            "top_expensive_nodes": self._get_top_expensive_nodes(5),

            # Iteration analysis (shows refinement costs)
            "iteration_costs": self._analyze_iteration_costs(),

            # Timing
            "workflow_duration_seconds": (
                (datetime.utcnow() - self.current_workflow["start_time"]).total_seconds()
                if self.current_workflow.get("start_time") else None
            )
        }

        return summary

    def _get_top_expensive_nodes(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get the top N most expensive nodes"""
        sorted_nodes = sorted(
            self.costs_by_node.items(),
            key=lambda x: x[1]["total_cost"],
            reverse=True
        )

        return [
            {
                "node": name,
                "cost": round(data["total_cost"], 6),
                "tokens": data["total_tokens"],
                "calls": data["calls"]
            }
            for name, data in sorted_nodes[:n]
        ]

    def _analyze_iteration_costs(self) -> Dict[str, Any]:
        """Analyze costs from iterative refinement"""
        if not self.costs_by_iteration:
            return None

        # Group by node
        iterations_by_node = defaultdict(list)
        for key, data in self.costs_by_iteration.items():
            node_name = key.rsplit("_iter_", 1)[0]
            iterations_by_node[node_name].append(data)

        analysis = {}
        for node, iterations in iterations_by_node.items():
            analysis[node] = {
                "total_iterations": len(iterations),
                "total_iteration_cost": round(
                    sum(it["total_cost"] for it in iterations), 6
                ),
                "avg_cost_per_iteration": round(
                    sum(it["total_cost"] for it in iterations) / len(iterations), 6
                )
            }

        return analysis

    def get_section_costs(self) -> Dict[str, Any]:
        """Get detailed costs for blog sections"""
        return {
            section: {
                "cost": round(data["total_cost"], 6),
                "tokens": data["total_tokens"]
            }
            for section, data in self.costs_by_section.items()
        }

    def get_cost_by_model(self) -> Dict[str, Any]:
        """Get cost breakdown by model type"""
        model_costs = defaultdict(lambda: {"cost": 0, "tokens": 0, "calls": 0})

        for call in self.call_history:
            model = call.get("model", "unknown")
            model_costs[model]["cost"] += call.get("total_cost", 0)
            model_costs[model]["tokens"] += call.get("total_tokens", 0)
            model_costs[model]["calls"] += 1

        return {
            model: {
                "cost": round(data["cost"], 6),
                "tokens": data["tokens"],
                "calls": data["calls"]
            }
            for model, data in model_costs.items()
        }

    def export_detailed_report(self) -> str:
        """Export a detailed cost report as JSON"""
        report = {
            "summary": self.get_workflow_summary(),
            "by_model": self.get_cost_by_model(),
            "section_costs": self.get_section_costs(),
            "call_history_sample": self.call_history[:10],  # First 10 calls as sample
            "timestamp": datetime.utcnow().isoformat()
        }

        return json.dumps(report, indent=2)

    def reset(self):
        """Reset all tracking for a new workflow"""
        self.__init__()
