# -*- coding: utf-8 -*-
"""
LangGraph definition for the Blog Refinement Agent.
Imports node functions from nodes.py and defines the graph structure.
"""
import logging
from langgraph.graph import StateGraph, END

from root.backend.agents.blog_refinement.state import BlogRefinementState
from root.backend.agents.blog_refinement.nodes import (
    generate_introduction_node,
    generate_conclusion_node,
    generate_summary_node,
    generate_titles_node,
    suggest_clarity_flow_node,
    reduce_redundancy_node,
    assemble_refined_draft_node
)

logger = logging.getLogger(__name__)

# --- Graph Creation ---

async def create_refinement_graph() -> StateGraph:
    """Creates the LangGraph StateGraph for the blog refinement process."""
    graph = StateGraph(BlogRefinementState)

    graph.add_node("generate_introduction", generate_introduction_node)
    graph.add_node("generate_conclusion", generate_conclusion_node)
    graph.add_node("generate_summary", generate_summary_node)
    graph.add_node("generate_titles", generate_titles_node)
    graph.add_node("suggest_clarity_flow", suggest_clarity_flow_node)
    graph.add_node("reduce_redundancy", reduce_redundancy_node)
    graph.add_node("assemble_draft", assemble_refined_draft_node)

    # --- Define Conditional Logic ---
    def should_continue(state: BlogRefinementState) -> str:
        """Determines whether to continue to the next step or end due to error."""
        if state.error:
            logger.error(f"Error detected in state, ending graph execution: {state.error}")
            return "end_due_to_error"
        else:
            return "continue"

    # --- Define Edges with Conditionals ---
    graph.set_entry_point("generate_introduction")
    graph.add_edge("generate_introduction", "generate_conclusion")
    graph.add_edge("generate_conclusion", "generate_summary")
    graph.add_edge("generate_summary", "generate_titles")
    graph.add_edge("generate_titles", "assemble_draft") # Titles goes to assemble
    graph.add_edge("assemble_draft", "reduce_redundancy") # Assemble goes to redundancy reduction
    graph.add_edge("reduce_redundancy", "suggest_clarity_flow") # Redundancy reduction goes to clarity/flow
    graph.add_edge("suggest_clarity_flow", END) # Clarity/flow is the last step before END

    # Compile the graph into a runnable application
    app = graph.compile()
    logger.info("Blog Refinement Graph compiled successfully.")
    return app
