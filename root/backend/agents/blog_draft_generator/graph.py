from langgraph.graph import StateGraph
from root.backend.agents.blog_draft_generator.nodes import (
    semantic_content_mapper,
    section_generator,
    content_enhancer,
    code_example_extractor,
    image_placeholder_generator,
    quality_validator,
    auto_feedback_generator,
    feedback_incorporator,
    section_finalizer,
    transition_generator,
    blog_compiler
)
from typing import Dict, Literal, Union
from root.backend.agents.blog_draft_generator.state import BlogDraftState

def should_continue_iteration(state: BlogDraftState) -> Union[Literal["continue_iteration"], Literal["finalize_section"]]:
    """Conditional routing based on iteration count."""
    # Log the current iteration count and max iterations
    print(f"should_continue_iteration - Current iteration: {state.iteration_count}, Max iterations: {state.max_iterations}")
    
    # Force finalization if we've reached or exceeded max iterations
    if state.iteration_count >= state.max_iterations:
        print(f"Max iterations ({state.max_iterations}) reached or exceeded, finalizing section")
        return "finalize_section"
    
    # Check if quality metrics indicate the section is good enough
    if hasattr(state.current_section, 'quality_metrics') and state.current_section.quality_metrics:
        overall_score = state.current_section.quality_metrics.get('overall_score', 0.0)
        print(f"Quality overall_score: {overall_score}")
        if overall_score >= 0.85:  # If quality is high enough, finalize even before max iterations
            print(f"Quality score {overall_score} >= 0.85, finalizing section early")
            return "finalize_section"
    
    # Otherwise, continue with auto-feedback
    print("Continuing iteration with auto-feedback")
    return "continue_iteration"

def should_generate_next_section(state: BlogDraftState) -> Union[Literal["next_section"], Literal["compile_blog"]]:
    """Conditional routing based on section completion."""
    if state.current_section_index < len(state.outline.sections):
        return "next_section"
    return "compile_blog"

async def create_draft_graph() -> StateGraph:
    """Creates the enhanced workflow graph for draft generation"""
    builder = StateGraph(BlogDraftState)
    
    # Add all nodes
    builder.add_node("semantic_mapper", semantic_content_mapper)
    builder.add_node("generator", section_generator)
    builder.add_node("enhancer", content_enhancer)
    builder.add_node("code_extractor", code_example_extractor)
    builder.add_node("image_placeholder", image_placeholder_generator)
    builder.add_node("validator", quality_validator)
    builder.add_node("auto_feedback", auto_feedback_generator)
    builder.add_node("feedback_inc", feedback_incorporator)
    builder.add_node("finalizer", section_finalizer)
    builder.add_node("transition_gen", transition_generator)
    builder.add_node("compiler", blog_compiler)
    
    # Set entry point
    builder.set_entry_point("semantic_mapper")
    
    # Define conditional edges for iteration control
    builder.add_conditional_edges(
        "validator",
        should_continue_iteration,
        {
            "continue_iteration": "auto_feedback",
            "finalize_section": "finalizer"
        }
    )
    
    # Define conditional edges for section progression
    builder.add_conditional_edges(
        "transition_gen",
        should_generate_next_section,
        {
            "next_section": "generator",
            "compile_blog": "compiler"
        }
    )
    
    # Define main workflow
    builder.add_edge("semantic_mapper", "generator")
    builder.add_edge("generator", "enhancer")
    builder.add_edge("enhancer", "code_extractor")
    builder.add_edge("code_extractor", "image_placeholder")
    builder.add_edge("image_placeholder", "validator")
    builder.add_edge("auto_feedback", "feedback_inc")
    builder.add_edge("feedback_inc", "validator")  # Loop back for iteration
    builder.add_edge("finalizer", "transition_gen")
    
    return builder.compile()
