# ABOUTME: FastMCP tools for blog section drafting and management
# ABOUTME: Provides MCP tools to draft, retrieve, and regenerate individual blog sections

from typing import Optional, Dict, Any, List
import logging
from mcp.server.fastmcp import FastMCP

from ..api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("section-tools")

# Backend client will be initialized per request using context manager


@mcp.tool()
async def draft_section(
    project_id: str,
    section_index: int,
    max_iterations: int = 3,
    quality_threshold: float = 0.8
) -> Dict[str, Any]:
    """
    Generate a draft for a specific blog section.

    This tool drafts a single section from the blog outline. The section is generated
    using the project's processed content (notebook/markdown files) and the outline structure.
    The draft goes through iterative refinement based on quality scoring.

    Args:
        project_id: The unique identifier for the project. Must have an outline generated first.
        section_index: The index of the section to draft (0-based). For example, 0 for the first
                      main section after the introduction.
        max_iterations: Maximum number of refinement iterations for quality improvement (default: 3).
                       Higher values may produce better quality but take longer.
        quality_threshold: Minimum quality score required (0.0-1.0, default: 0.8).
                          The section will be refined until it meets this threshold
                          or max_iterations is reached.

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - section_index: The index of the drafted section
        - section_title: The title of the section
        - content: The generated section content
        - quality_score: The final quality score achieved
        - iterations_used: Number of refinement iterations performed
        - metadata: Additional information about the generation

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the section_index is invalid or outline doesn't exist

    Example:
        result = await draft_section(
            project_id="abc123",
            section_index=0,
            max_iterations=5,
            quality_threshold=0.85
        )
        print(f"Section: {result['section_title']}")
        print(f"Quality: {result['quality_score']}")
    """
    try:
        async with BackendAPIClient() as client:
            # Draft the section
            result = await client.draft_section(
                project_id=project_id,
                section_index=section_index,
                max_iterations=max_iterations,
                quality_threshold=quality_threshold
            )

            if "error" in result:
                return {
                    "error": result["error"],
                    "project_id": project_id,
                    "section_index": section_index
                }

            logger.info(f"Successfully drafted section {section_index} for project {project_id}")
            return result

    except Exception as e:
        logger.error(f"Error during section draft: {e}")
        return {
            "error": f"Failed to draft section: {str(e)}",
            "project_id": project_id,
            "section_index": section_index
        }


@mcp.tool()
async def get_section(
    project_id: str,
    section_index: int
) -> Dict[str, Any]:
    """
    Retrieve a specific drafted section by its index.

    This tool fetches a previously drafted section from the project. Use this to review
    section content before regenerating or to retrieve sections for editing.

    Args:
        project_id: The unique identifier for the project.
        section_index: The index of the section to retrieve (0-based).

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - section_index: The index of the section
        - section_title: The title of the section
        - content: The section content
        - status: The section status (drafted, reviewed, etc.)
        - quality_score: The quality score if available
        - created_at: Timestamp when section was created
        - updated_at: Timestamp when section was last updated

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the section doesn't exist

    Example:
        result = await get_section(
            project_id="abc123",
            section_index=1
        )
        if "error" not in result:
            print(f"Section title: {result['section_title']}")
            print(f"Content length: {len(result['content'])} characters")
    """
    try:
        async with BackendAPIClient() as client:
            # Get the specific section
            section = await client.get_section(
                project_id=project_id,
                section_index=section_index
            )

            if section is None:
                return {
                    "error": f"Section {section_index} not found for project {project_id}. "
                            "Make sure the section has been drafted first.",
                    "project_id": project_id,
                    "section_index": section_index
                }

            logger.info(f"Successfully retrieved section {section_index} for project {project_id}")
            return {
                "project_id": project_id,
                "section": section,
                **section  # Unpack section data into the response
            }

    except Exception as e:
        logger.error(f"Error retrieving section: {e}")
        return {
            "error": f"Failed to retrieve section: {str(e)}",
            "project_id": project_id,
            "section_index": section_index
        }


@mcp.tool()
async def regenerate_section(
    project_id: str,
    section_index: int,
    feedback: str,
    max_iterations: int = 3,
    quality_threshold: float = 0.8
) -> Dict[str, Any]:
    """
    Regenerate a section with user feedback.

    This tool regenerates a previously drafted section incorporating user feedback.
    Use this when you want to improve or adjust a section based on specific requirements
    or critiques. The regeneration process uses the feedback to guide improvements.

    Args:
        project_id: The unique identifier for the project.
        section_index: The index of the section to regenerate (0-based).
        feedback: User feedback to guide the regeneration. Required. Be specific about
                 what needs to be changed. Examples:
                 - "Add more code examples and make explanations simpler"
                 - "Reduce technical jargon and add real-world use cases"
                 - "Expand the performance optimization section with benchmarks"
        max_iterations: Maximum refinement iterations (default: 3).
        quality_threshold: Minimum quality score required (0.0-1.0, default: 0.8).

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - section_index: The index of the regenerated section
        - section_title: The title of the section
        - content: The regenerated section content
        - quality_score: The final quality score achieved
        - iterations_used: Number of refinement iterations performed
        - feedback_applied: The feedback that was used for regeneration
        - previous_version: Reference to the previous version if available

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the section doesn't exist or feedback is empty

    Example:
        result = await regenerate_section(
            project_id="abc123",
            section_index=2,
            feedback="Add more practical examples and simplify the technical explanations"
        )
        print(f"Regenerated: {result['section_title']}")
        print(f"New quality score: {result['quality_score']}")
    """
    if not feedback or not feedback.strip():
        return {
            "error": "feedback parameter is required and cannot be empty",
            "project_id": project_id,
            "section_index": section_index
        }

    try:
        async with BackendAPIClient() as client:
            # NOTE: The regenerate_section_with_feedback endpoint is currently deprecated
            # in the backend (returns 501). For now, we'll attempt to use it anyway,
            # but this will likely need backend updates to work properly.

            # Get project to find project name
            project_data = await client.get_project(project_id)

            if "error" in project_data:
                return {
                    "error": project_data["error"],
                    "project_id": project_id,
                    "section_index": section_index
                }

            project_name = project_data.get("project", {}).get("name")

            url = f"{client.base_url}/regenerate_section_with_feedback/{project_name}"

            data = {
                "job_id": project_id,  # Using project_id as job_id until backend is migrated
                "section_index": section_index,
                "feedback": feedback,
                "max_iterations": max_iterations,
                "quality_threshold": quality_threshold
            }

            # Make the request
            async with client.session.post(url, data=data) as response:
                result = await response.json()

                if response.status == 501:
                    return {
                        "error": "Section regeneration endpoint is currently deprecated. "
                                "This feature needs backend migration to work with project-based architecture. "
                                "As a workaround, you can draft the section again with adjusted parameters.",
                        "project_id": project_id,
                        "section_index": section_index,
                        "status_code": 501
                    }

                if "error" in result:
                    return {
                        "error": result["error"],
                        "project_id": project_id,
                        "section_index": section_index
                    }

                logger.info(f"Successfully regenerated section {section_index} for project {project_id}")
                return result

    except Exception as e:
        logger.error(f"Error during section regeneration: {e}")
        return {
            "error": f"Failed to regenerate section: {str(e)}",
            "project_id": project_id,
            "section_index": section_index
        }


@mcp.tool()
async def get_all_sections(project_id: str) -> Dict[str, Any]:
    """
    Retrieve all drafted sections for a project.

    This tool fetches all sections that have been drafted for a project, providing
    a complete overview of the blog content. Use this to review all sections at once
    or to check which sections have been drafted.

    Args:
        project_id: The unique identifier for the project.

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - total_sections: Total number of sections
        - drafted_sections: Number of sections that have been drafted
        - sections: List of section objects, each containing:
            - section_index: The index of the section
            - section_title: The title of the section
            - content: The section content (if drafted)
            - status: The section status
            - quality_score: Quality score if available
            - created_at: Creation timestamp
            - updated_at: Last update timestamp

    Raises:
        ConnectionError: If unable to connect to the backend API

    Example:
        result = await get_all_sections(project_id="abc123")
        print(f"Total sections: {result['total_sections']}")
        print(f"Drafted: {result['drafted_sections']}")
        for section in result['sections']:
            status = "✓" if section.get('content') else "✗"
            print(f"{status} Section {section['section_index']}: {section['section_title']}")
    """
    try:
        async with BackendAPIClient() as client:
            # Get all sections
            sections = await client.get_all_sections(project_id)

            # Calculate statistics
            total_sections = len(sections)
            drafted_sections = sum(1 for s in sections if s.get("content"))

            logger.info(f"Successfully retrieved {total_sections} sections for project {project_id}")
            return {
                "project_id": project_id,
                "total_sections": total_sections,
                "drafted_sections": drafted_sections,
                "sections": sections
            }

    except Exception as e:
        logger.error(f"Error retrieving all sections: {e}")
        return {
            "error": f"Failed to retrieve sections: {str(e)}",
            "project_id": project_id
        }
