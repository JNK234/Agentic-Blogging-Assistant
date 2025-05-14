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
    suggest_clarity_flow_node, # Import the new node function
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
    graph.add_node("suggest_clarity_flow", partial(suggest_clarity_flow_node, model=model)) # Add the new node
    # This node doesn't need the model, so no binding is necessary
    graph.add_node("assemble_draft", assemble_refined_draft_node)

    # Define edges for the sequential flow
    graph.set_entry_point("generate_introduction")
    graph.add_edge("generate_introduction", "generate_conclusion")
    graph.add_edge("generate_conclusion", "generate_summary")
    graph.add_edge("generate_summary", "generate_titles")
    graph.add_edge("generate_titles", "assemble_draft") # Titles goes to assemble
    graph.add_edge("assemble_draft", "suggest_clarity_flow") # Assemble goes to clarity/flow
    graph.add_edge("suggest_clarity_flow", END) # Clarity/flow is the last step before END

    # Compile the graph into a runnable application
    app = graph.compile()
    logger.info("Blog Refinement Graph compiled successfully.")
    return app
