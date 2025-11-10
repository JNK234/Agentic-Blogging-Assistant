# ABOUTME: Wrapper for LLM models that automatically tracks token usage and costs
# ABOUTME: Works with all model providers, integrates with LangGraph state and SQL tracking

from typing import Any, Dict, Optional, Callable
from datetime import datetime
import logging
import asyncio
from langchain.schema import AIMessage, BaseMessage
from backend.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)

class CostTrackingModel:
    """
    Wrapper for any LLM model that tracks token usage and costs.
    Designed to work seamlessly with LangGraph state management and SQL persistence.
    """

    def __init__(self, base_model: Any, model_name: str,
                 cost_aggregator: Optional = None,
                 context_supplier: Optional[Callable[[], Dict[str, Any]]] = None,
                 sql_project_manager: Optional = None,
                 project_id: Optional[str] = None,
                 agent_name: Optional[str] = None):
        """
        Initialize cost-tracking wrapper

        Args:
            base_model: The underlying LLM model (OpenAI, Claude, etc.)
            model_name: Name of the model for pricing lookup
            cost_aggregator: Optional aggregator for collecting costs
            context_supplier: Optional function to provide tracking context
            sql_project_manager: Optional SQL project manager for persistent tracking
            project_id: Project ID for SQL tracking
            agent_name: Agent name for SQL tracking
        """
        self.base_model = base_model
        self.model_name = self._normalize_model_name(model_name)
        self.token_counter = TokenCounter()
        self.cost_aggregator = cost_aggregator
        self.context_supplier = context_supplier

        # SQL tracking support
        self.sql_project_manager = sql_project_manager
        self.project_id = project_id
        self.agent_name = agent_name

        # Track costs for this model instance
        self.session_costs = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "calls": []
        }

    def configure_tracking(self,
                            cost_aggregator: Optional = None,
                            context_supplier: Optional[Callable[[], Dict[str, Any]]] = None,
                            sql_project_manager: Optional = None,
                            project_id: Optional[str] = None,
                            agent_name: Optional[str] = None) -> None:
        """Update cost aggregator, context supplier, and SQL tracking at runtime."""
        if cost_aggregator is not None:
            self.cost_aggregator = cost_aggregator
        if context_supplier is not None:
            self.context_supplier = context_supplier
        if sql_project_manager is not None:
            self.sql_project_manager = sql_project_manager
        if project_id is not None:
            self.project_id = project_id
        if agent_name is not None:
            self.agent_name = agent_name

    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name for pricing lookup"""
        try:
            return self.token_counter._normalize_model_name(model_name)
        except Exception:
            return model_name

    async def ainvoke(self, prompt: str, **kwargs) -> AIMessage:
        """
        Async invoke with automatic cost tracking

        Extracts tracking context from kwargs if available (for LangGraph integration)
        """
        start_time = datetime.utcnow()
        call_context = kwargs.pop('_tracking_context', None)
        if call_context is None and self.context_supplier:
            try:
                call_context = self.context_supplier() or {}
            except Exception as err:
                logger.debug(f"Failed to resolve tracking context: {err}")
                call_context = {}
        call_context = call_context or {}

        # Count input tokens
        input_tokens = self.token_counter.count_tokens(prompt, self.model_name)

        try:
            # Call the underlying model
            response = await self.base_model.ainvoke(prompt, **kwargs)

            # Extract response text
            if isinstance(response, BaseMessage):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            # Count output tokens
            output_tokens = self.token_counter.count_tokens(response_text, self.model_name)

            # Calculate cost
            total_cost, breakdown = self.token_counter.calculate_cost(
                input_tokens, output_tokens, self.model_name
            )

            # Record the call
            call_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "model": self.model_name,
                "latency_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
                **breakdown,
                **call_context  # Include LangGraph context
            }

            # Update session totals
            self.session_costs["total_calls"] += 1
            self.session_costs["total_tokens"] += breakdown["total_tokens"]
            self.session_costs["total_cost"] += total_cost
            self.session_costs["calls"].append(call_record)

            # Send to aggregator if available
            if self.cost_aggregator:
                self.cost_aggregator.record_cost(call_record)

            # Track in SQL database if available
            if self.sql_project_manager and self.project_id:
                try:
                    await self.sql_project_manager.track_cost(
                        project_id=self.project_id,
                        agent_name=self.agent_name or "unknown_agent",
                        operation=call_context.get('node_name', 'llm_call'),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost=total_cost,
                        model_used=self.model_name,
                        metadata={
                            "latency_ms": call_record["latency_ms"],
                            "context": call_context
                        }
                    )
                except Exception as sql_error:
                    # Log warning but don't fail the call
                    logger.warning(f"SQL cost tracking failed: {sql_error}")

            # Log the cost
            logger.info(
                f"LLM Call: {self.model_name} | "
                f"Tokens: {input_tokens}/{output_tokens} | "
                f"Cost: ${total_cost:.6f} | "
                f"Context: {call_context.get('node_name', 'unknown')}"
            )

            # Attach usage metadata to response if possible
            if hasattr(response, '__dict__') and isinstance(response, BaseMessage):
                response.usage_metadata = breakdown

            return response

        except Exception as e:
            # Still track the failed call
            call_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "model": self.model_name,
                "input_tokens": input_tokens,
                "output_tokens": 0,
                "total_cost": (input_tokens / 1000) *
                            self.token_counter.PRICING.get(self.model_name, {"input": 0.001})["input"],
                "error": str(e),
                **call_context
            }

            self.session_costs["total_calls"] += 1
            self.session_costs["calls"].append(call_record)

            logger.error(f"LLM call failed: {e}")
            raise

    def invoke(self, prompt: str, **kwargs):
        """Sync version of invoke"""
        return asyncio.run(self.ainvoke(prompt, **kwargs))

    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of all costs for this model instance"""
        return {
            "model": self.model_name,
            "total_calls": self.session_costs["total_calls"],
            "total_tokens": self.session_costs["total_tokens"],
            "total_cost": self.session_costs["total_cost"],
            "avg_cost_per_call": (
                self.session_costs["total_cost"] / self.session_costs["total_calls"]
                if self.session_costs["total_calls"] > 0 else 0
            )
        }

    def reset_session_costs(self):
        """Reset the session cost tracking"""
        self.session_costs = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "calls": []
        }
