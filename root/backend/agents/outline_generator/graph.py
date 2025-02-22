from langgraph.graph import StateGraph, END
from .nodes import analyze_content, difficulty_assessor, prerequisite_identifier, outline_structurer, final_generator
from .state import OutlineState
from typing import Union

def create_outline_graph() -> StateGraph:
    """Creates the outline generation graph."""
    graph = StateGraph(OutlineState)

    
    graph.add_node("analyze_content", analyze_content)
    graph.add_node("assess_difficulty", difficulty_assessor)
    graph.add_node("identify_prerequisites", prerequisite_identifier)
    graph.add_node("structure_outline", outline_structurer)
    graph.add_node("generate_final", final_generator)

    graph.set_entry_point("analyze_content")
    
    graph.add_edge("analyze_content", "assess_difficulty")
    graph.add_edge("assess_difficulty", "identify_prerequisites")
    graph.add_edge("identify_prerequisites", "structure_outline")
    graph.add_edge("structure_outline", "generate_final")
    graph.add_edge("generate_final", END)
    
    return graph.compile()
