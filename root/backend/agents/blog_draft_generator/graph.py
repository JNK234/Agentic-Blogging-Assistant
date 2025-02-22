from langgraph.graph import Graph
from root.backend.agents.blog_draft_generator.nodes import map_content_to_sections, section_generator, content_enhancer, feedback_incorporator, section_finalizer
from typing import Dict

def create_draft_graph() -> Graph:
    """Creates the workflow graph for draft generation"""
    builder = Graph()
    builder.add_node("content_mapper", map_content_to_sections)
    builder.add_node("generator", section_generator)
    builder.add_node("enhancer", content_enhancer)
    builder.add_node("feedback", feedback_incorporator)
    builder.add_node("finalizer", section_finalizer)

    builder.set_entry_point("content_mapper")

    builder.add_edge("content_mapper", "generator")
    builder.add_edge("generator", "enhancer")
    builder.add_edge("enhancer", "feedback")
    builder.add_edge("feedback", "finalizer")
    #builder.add_edge("finalizer", "generator")  # Loop back to generate next section
    builder.add_edge("finalizer", "generator")

    return builder.compile()
