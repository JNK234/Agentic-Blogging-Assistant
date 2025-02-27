"""
Graph definition for content parsing.
"""
from langgraph.graph import StateGraph, END, START
from .nodes import (
    validate_file,
    parse_content,
    chunk_content,
    prepare_metadata,
    store_content
)
from .state import ContentParsingState

async def create_parsing_graph(state_class=ContentParsingState) -> StateGraph:
    """Creates the content parsing graph."""
    graph = StateGraph(state_class)
    
    # Add nodes
    graph.add_node("validate", validate_file)
    graph.add_node("parse", parse_content)
    graph.add_node("chunk", chunk_content)
    graph.add_node("prepare_metadata", prepare_metadata)
    graph.add_node("store", store_content)
    
    # Add edges
    # graph.add_edge(START, "validate")
    graph.add_edge("validate", "parse")
    graph.add_edge("parse", "chunk")
    graph.add_edge("chunk", "prepare_metadata")
    graph.add_edge("prepare_metadata", "store")
    graph.add_edge("store", END)
    
    graph.set_entry_point("validate")
    # graph.set_finish_point("store")

    return graph.compile()
