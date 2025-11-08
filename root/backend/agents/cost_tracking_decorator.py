# ABOUTME: Decorator for automatic cost tracking in LangGraph nodes
# ABOUTME: Wraps node functions to track costs and update state automatically

from functools import wraps
from typing import Callable, Any, TypeVar
import logging
from datetime import datetime
import asyncio
from root.backend.models.cost_tracking_wrapper import CostTrackingModel
from root.backend.services.cost_aggregator import CostAggregator

logger = logging.getLogger(__name__)

StateType = TypeVar('StateType')

def track_node_costs(node_name: str, agent_name: str = None, stage: str = None):
    """
    Decorator to automatically track costs for a LangGraph node.

    Args:
        node_name: Name of the node for tracking
        agent_name: Optional agent name (will use state.current_agent_name if not provided)
        stage: Optional stage label for aggregation (outline, drafting, refinement, etc.)

    Usage:
        @track_node_costs("section_generator")
        async def section_generator(state: BlogDraftState) -> BlogDraftState:
            # Your node logic here
            response = await state.model.ainvoke(prompt)
            return state
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(state: StateType) -> StateType:
            # Start timing
            start_time = datetime.utcnow()

            # Set node context in state
            if hasattr(state, 'current_node_name'):
                state.current_node_name = node_name

            if stage and hasattr(state, 'current_stage'):
                state.current_stage = stage

            if agent_name and hasattr(state, 'current_agent_name'):
                state.current_agent_name = agent_name
            elif not hasattr(state, 'current_agent_name'):
                state.current_agent_name = 'unknown'

            # Ensure cost aggregator exists
            if hasattr(state, 'ensure_cost_aggregator'):
                project_id = getattr(state, 'project_id', None) or getattr(state, 'project_name', None) or 'unknown'
                state.ensure_cost_aggregator(project_id=project_id)
            elif hasattr(state, 'cost_aggregator') and not state.cost_aggregator:
                state.cost_aggregator = CostAggregator()
                state.cost_aggregator.start_workflow(
                    project_id=getattr(state, 'project_id', 'unknown')
                )

            # Wrap the model with cost tracking if not already wrapped
            if hasattr(state, 'model') and state.model:
                if not isinstance(state.model, CostTrackingModel):
                    model_name = getattr(state.model, 'model_name', 'unknown')
                    if hasattr(state.model, 'llm'):
                        # Handle wrapped models (like from model_factory)
                        model_name = getattr(state.model.llm, 'model_name', model_name)

                    state.model = CostTrackingModel(
                        base_model=state.model,
                        model_name=model_name,
                        cost_aggregator=getattr(state, 'cost_aggregator', None)
                    )

                # Inject tracking context into the model
                if hasattr(state.model, 'configure_tracking'):
                    context_supplier = getattr(state, 'get_tracking_context', None)
                    sql_pm = getattr(state, 'sql_project_manager', None)
                    proj_id = getattr(state, 'project_id', None)
                    current_agent = getattr(state, 'current_agent_name', agent_name or 'unknown')

                    state.model.configure_tracking(
                        cost_aggregator=getattr(state, 'cost_aggregator', None),
                        context_supplier=context_supplier,
                        sql_project_manager=sql_pm,
                        project_id=proj_id,
                        agent_name=current_agent
                    )
                else:
                    if hasattr(state.model, 'cost_aggregator'):
                        state.model.cost_aggregator = getattr(state, 'cost_aggregator', None)
                    if hasattr(state.model, 'context_supplier') and hasattr(state, 'get_tracking_context'):
                        state.model.context_supplier = state.get_tracking_context

            # Log node entry
            logger.info(f"Entering node: {state.current_agent_name}.{node_name}")

            try:
                # Execute the actual node function
                result = await func(state)

                # Update cost summary in state
                if hasattr(result, 'update_cost_summary'):
                    result.update_cost_summary()

                # Log node cost
                if hasattr(result, 'get_node_cost'):
                    node_cost = result.get_node_cost(node_name)
                    if node_cost > 0:
                        logger.info(
                            f"Node {state.current_agent_name}.{node_name} "
                            f"completed. Cost: ${node_cost:.6f}"
                        )

                # Log timing
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.debug(f"Node {node_name} execution time: {duration:.2f}s")

                return result

            except Exception as e:
                logger.error(f"Error in node {node_name}: {e}")
                raise

        # Handle sync functions
        @wraps(func)
        def sync_wrapper(state: StateType) -> StateType:
            import asyncio
            return asyncio.run(async_wrapper(state))

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_iteration_costs(func: Callable) -> Callable:
    """
    Special decorator for tracking iterative refinement costs.

    Use this in addition to @track_node_costs for nodes that iterate.
    """
    @wraps(func)
    async def wrapper(state: StateType) -> StateType:
        # Track iteration number
        if hasattr(state, 'iteration_count'):
            if hasattr(state, 'current_iteration'):
                state.current_iteration = state.iteration_count

        result = await func(state)

        # Log iteration cost if applicable
        if hasattr(state, 'cost_aggregator') and hasattr(state, 'iteration_count'):
            iteration_costs = state.cost_aggregator._analyze_iteration_costs()
            if iteration_costs:
                current_node = getattr(state, 'current_node_name', 'unknown')
                node_key = f"{state.current_agent_name}.{current_node}"
                if node_key in iteration_costs:
                    logger.info(
                        f"Iteration {state.iteration_count} cost: "
                        f"${iteration_costs[node_key]['avg_cost_per_iteration']:.6f}"
                    )

        return result

    return wrapper
