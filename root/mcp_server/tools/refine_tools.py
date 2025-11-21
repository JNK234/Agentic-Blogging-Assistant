# ABOUTME: FastMCP tools for blog refinement and title generation
# ABOUTME: Provides MCP tools to refine sections and generate title options

from typing import Optional, Dict, Any
import logging
from mcp.server.fastmcp import FastMCP

from ..api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("refine-tools")

# Backend client will be initialized per request using context manager


@mcp.tool()
async def refine_section(
    project_id: str,
    section_index: int,
    focus: str = "overall"
) -> Dict[str, Any]:
    """
    Refine a specific section of the blog draft with targeted feedback.

    This tool regenerates a specific section with refinement feedback to improve
    quality, clarity, or style. The focus parameter allows you to specify what
    aspect of the section should be improved.

    Args:
        project_id: The unique identifier for the project. This should be obtained after
                   generating the blog draft. Use the project_id from previous operations.
        section_index: The index of the section to refine (0-based). For example,
                      section_index=0 is the first main section (usually the introduction),
                      section_index=1 is the second section, etc.
        focus: The aspect to focus on during refinement. Options include:
              - "overall": General quality improvement (default)
              - "clarity": Improve readability and clarity
              - "technical": Add more technical depth and examples
              - "concise": Make the section more concise
              - "engaging": Make the content more engaging and reader-friendly
              - "examples": Add more practical examples and code snippets
              Custom feedback can also be provided as a string.

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - section_index: Index of the refined section
        - title: Section title
        - content: The refined section content
        - regenerated_at: Timestamp of regeneration
        - feedback_provided: The feedback that was used for refinement

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response or section doesn't exist

    Example:
        # Refine the introduction section for better clarity
        result = await refine_section(
            project_id="abc123",
            section_index=0,
            focus="clarity"
        )

        # Add more technical depth to the second section
        result = await refine_section(
            project_id="abc123",
            section_index=1,
            focus="technical"
        )

        # Custom feedback for a specific section
        result = await refine_section(
            project_id="abc123",
            section_index=2,
            focus="Add more real-world use cases and expand on the benefits"
        )
    """
    # Map focus keywords to detailed feedback
    focus_map = {
        "overall": "Improve overall quality, clarity, and flow of this section",
        "clarity": "Enhance clarity and readability. Simplify complex concepts and use clearer language",
        "technical": "Add more technical depth, code examples, and detailed explanations",
        "concise": "Make the content more concise while preserving key information",
        "engaging": "Make the content more engaging and reader-friendly with better storytelling",
        "examples": "Add more practical examples, code snippets, and real-world use cases"
    }

    # Use mapped feedback or custom feedback string
    feedback = focus_map.get(focus.lower(), focus)

    try:
        async with BackendAPIClient() as client:
            # Get project details to verify it exists and get project name
            project_data = await client.get_project(project_id)

            if "error" in project_data:
                return {
                    "error": project_data["error"],
                    "project_id": project_id
                }

            project_name = project_data.get("project", {}).get("name")
            if not project_name:
                return {
                    "error": "Project name not found in project data",
                    "project_id": project_id
                }

            # Verify the section exists
            sections = project_data.get("project", {}).get("sections", [])
            section_exists = any(s.get("section_index") == section_index for s in sections)

            if not section_exists:
                return {
                    "error": f"Section {section_index} not found. Available sections: {len(sections)}",
                    "project_id": project_id,
                    "available_sections": len(sections)
                }

            # Call the backend API endpoint for section regeneration
            # Note: This uses a different pattern than other methods since it requires
            # form data with job_id, section_index, and feedback
            url = f"{client.base_url}/regenerate_section_with_feedback/{project_name}"

            import aiohttp
            data = aiohttp.FormData()
            data.add_field("job_id", project_id)
            data.add_field("section_index", str(section_index))
            data.add_field("feedback", feedback)
            data.add_field("max_iterations", "3")
            data.add_field("quality_threshold", "0.8")

            async with client.session.post(url, data=data) as response:
                result = await response.json()

            logger.info(f"Successfully refined section {section_index} for project {project_id}")

            # Check if there's an error in the response
            if "error" in result:
                return {
                    "error": result["error"],
                    "project_id": project_id,
                    "section_index": section_index,
                    "note": "This endpoint may need migration. Try using the compile and refine workflow instead."
                }

            return {
                "project_id": project_id,
                "section_index": section_index,
                **result
            }

    except Exception as e:
        logger.error(f"Error during section refinement: {e}")
        return {
            "error": f"Failed to refine section: {str(e)}",
            "project_id": project_id,
            "section_index": section_index
        }


@mcp.tool()
async def generate_title_options(
    project_id: str,
    num_titles: int = 5
) -> Dict[str, Any]:
    """
    Generate multiple title options for a blog draft.

    This tool generates creative, SEO-friendly title options for a blog post.
    It analyzes the compiled blog draft and creates compelling titles that
    capture the essence of the content.

    Args:
        project_id: The unique identifier for the project. The blog must have
                   been compiled and drafted before generating title options.
        num_titles: Number of title options to generate (default: 5, range: 3-10).
                   More options provide more variety but take longer to generate.

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - title_options: List of title option objects, each containing:
          - title: The generated title text
          - rationale: Explanation of why this title works
          - style: The style category (e.g., "descriptive", "question", "how-to")
        - num_generated: Number of titles successfully generated
        - refined_draft: The refined blog content (if available)
        - summary: Blog summary (if available)

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response or blog not compiled

    Example:
        # Generate 5 title options
        result = await generate_title_options(project_id="abc123")
        for option in result['title_options']:
            print(f"{option['title']} - {option['rationale']}")

        # Generate more options for variety
        result = await generate_title_options(
            project_id="abc123",
            num_titles=8
        )
    """
    # Validate num_titles range
    if num_titles < 3:
        num_titles = 3
    elif num_titles > 10:
        num_titles = 10

    try:
        async with BackendAPIClient() as client:
            # Get project details to verify it exists and has a compiled draft
            project_data = await client.get_project(project_id)

            if "error" in project_data:
                return {
                    "error": project_data["error"],
                    "project_id": project_id
                }

            project_name = project_data.get("project", {}).get("name")
            if not project_name:
                return {
                    "error": "Project name not found in project data",
                    "project_id": project_id
                }

            # Check if blog has been compiled
            milestones = project_data.get("milestones", {})
            if "blog_refined" in milestones:
                # Already refined, return existing title options
                refined_data = milestones["blog_refined"]["data"]
                return {
                    "project_id": project_id,
                    "title_options": refined_data.get("title_options", []),
                    "num_generated": len(refined_data.get("title_options", [])),
                    "refined_draft": refined_data.get("refined_content"),
                    "summary": refined_data.get("summary"),
                    "was_cached": True,
                    "note": "These titles were generated during blog refinement"
                }

            # Check if sections are generated to compile a draft
            sections = project_data.get("project", {}).get("sections", [])
            if not sections:
                return {
                    "error": "No sections found. Generate blog sections first before creating title options.",
                    "project_id": project_id,
                    "has_sections": False
                }

            # Compile the draft from sections
            outline_data = milestones.get("outline_generated", {}).get("data", {}).get("outline", {})

            blog_parts = []
            # Add title (if available from outline)
            if outline_data.get("title"):
                blog_parts.append(f"# {outline_data['title']}\n\n")

            # Add table of contents
            blog_parts.append("## Table of Contents\n\n")
            for i, section_data in enumerate(sections):
                title = section_data.get("title", f"Section {i+1}")
                blog_parts.append(f"{i+1}. [{title}](#section-{i+1})\n")
            blog_parts.append("\n---\n\n")

            # Add sections
            for i, section_data in enumerate(sections):
                title = section_data.get("title", f"Section {i+1}")
                content = section_data.get("content", "")
                blog_parts.append(f"## {title}\n\n{content}\n\n")

            compiled_draft = "".join(blog_parts)

            # Prepare title configuration
            import json
            title_config = json.dumps({
                "num_titles": num_titles,
                "styles": ["descriptive", "question", "how-to", "listicle", "benefit-driven"]
            })

            # Call the refine_blog endpoint with title configuration
            url = f"{client.base_url}/refine_blog/{project_name}"

            import aiohttp
            data = aiohttp.FormData()
            data.add_field("job_id", project_id)
            data.add_field("compiled_draft", compiled_draft)
            data.add_field("title_config", title_config)

            async with client.session.post(url, data=data) as response:
                result = await response.json()

            if "error" in result:
                return {
                    "error": result["error"],
                    "project_id": project_id,
                    "details": result
                }

            logger.info(f"Successfully generated {len(result.get('title_options', []))} title options for project {project_id}")

            return {
                "project_id": project_id,
                "title_options": result.get("title_options", []),
                "num_generated": len(result.get("title_options", [])),
                "refined_draft": result.get("refined_draft"),
                "summary": result.get("summary"),
                "was_cached": False
            }

    except Exception as e:
        logger.error(f"Error during title generation: {e}")
        return {
            "error": f"Failed to generate title options: {str(e)}",
            "project_id": project_id
        }
