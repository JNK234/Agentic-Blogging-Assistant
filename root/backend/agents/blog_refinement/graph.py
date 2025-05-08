# -*- coding: utf-8 -*-
"""
LangGraph definition for the Blog Refinement Agent.
Imports node functions from nodes.py and defines the graph structure.
"""
import logging
from functools import partial
from pydantic import BaseModel
from langgraph.graph import StateGraph, END


# Assuming BaseModel is correctly imported where needed
from root.backend.agents.blog_refinement.state import BlogRefinementState
# Import node functions from nodes.py
from root.backend.agents.blog_refinement.nodes import (
    generate_introduction_node,
    generate_conclusion_node,
    generate_summary_node,
    generate_titles_node,
    assemble_refined_draft_node
)

logger = logging.getLogger(__name__)

# --- Graph Creation ---

async def create_refinement_graph(model: BaseModel) -> StateGraph:
    """
    Creates the LangGraph StateGraph for the blog refinement process.

    Args:
        model: An instance of the language model to be used by the nodes.

    Returns:
        A compiled LangGraph application (StateGraph).
    """

    graph = StateGraph(BlogRefinementState)

    # Add nodes, binding the model instance to nodes that require it using partial
    # This ensures the model is available when the node function is called by LangGraph
    graph.add_node("generate_introduction", partial(generate_introduction_node, model=model))
    graph.add_node("generate_conclusion", partial(generate_conclusion_node, model=model))
    graph.add_node("generate_summary", partial(generate_summary_node, model=model))
    graph.add_node("generate_titles", partial(generate_titles_node, model=model))
    # This node doesn't need the model, so no binding is necessary
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

    # After Introduction
    graph.add_conditional_edges(
        "generate_introduction",
        should_continue,
        {
            "continue": "generate_conclusion",
            "end_due_to_error": END,
        },
    )

    # After Conclusion
    graph.add_conditional_edges(
        "generate_conclusion",
        should_continue,
        {
            "continue": "generate_summary",
            "end_due_to_error": END,
        },
    )

    # After Summary
    graph.add_conditional_edges(
        "generate_summary",
        should_continue,
        {
            "continue": "generate_titles",
            "end_due_to_error": END,
        },
    )

    # After Titles
    graph.add_conditional_edges(
        "generate_titles",
        should_continue,
        {
            "continue": "assemble_draft",
            "end_due_to_error": END,
        },
    )

    # After Assembly (always ends)
    graph.add_edge("assemble_draft", END)

    # Compile the graph into a runnable application
    app = graph.compile()
    logger.info("Blog Refinement Graph compiled successfully.")
    return app
