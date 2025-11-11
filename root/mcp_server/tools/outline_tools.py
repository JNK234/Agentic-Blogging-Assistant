# ABOUTME: FastMCP tools for outline generation and management
# ABOUTME: Provides MCP tools to generate, retrieve, and regenerate blog outlines

from typing import Optional, Dict, Any
import logging
from mcp.server.fastmcp import FastMCP

from ..api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("outline-tools")

# Backend client will be initialized per request using context manager


@mcp.tool()
async def generate_outline(
    project_id: str,
    user_guidelines: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a blog outline for a project.

    This tool generates a structured blog outline from processed content (notebook and/or markdown files).
    The outline includes title, introduction, main sections, and conclusion.

    Args:
        project_id: The unique identifier for the project. This should be obtained after
                   uploading and processing files. Use the project_id from the upload response.
        user_guidelines: Optional guidelines or instructions for outline generation.
                        For example: "Focus on practical examples" or "Keep it beginner-friendly".

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - outline: The generated outline with sections
        - outline_hash: Hash of the outline for caching
        - was_cached: Whether the outline was retrieved from cache

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await generate_outline(
            project_id="abc123",
            user_guidelines="Focus on practical Python examples"
        )
    """
    try:
        async with BackendAPIClient() as client:
            # Generate outline using the existing API client method
            result = await client.generate_outline(
                project_id=project_id,
                user_guidelines=user_guidelines
            )

            logger.info(f"Successfully generated outline for project {project_id}")
            return result

    except Exception as e:
        logger.error(f"Error during outline generation: {e}")
        return {
            "error": f"Failed to generate outline: {str(e)}",
            "project_id": project_id
        }


@mcp.tool()
async def get_outline(project_id: str) -> Dict[str, Any]:
    """
    Retrieve the generated outline for a project.

    This tool fetches the outline that was previously generated for a project.
    It's useful for viewing the outline structure before proceeding with blog draft generation.

    Args:
        project_id: The unique identifier for the project.

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - outline: The outline object with sections
        - outline_title: The title of the outline
        - has_outline: Boolean indicating if outline exists
        - total_sections: Number of sections in the outline

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await get_outline(project_id="abc123")
        print(f"Outline title: {result['outline_title']}")
        print(f"Number of sections: {result['total_sections']}")
    """
    try:
        async with BackendAPIClient() as client:
            # Get project details including milestones
            project_data = await client.get_project(project_id)

            if "error" in project_data:
                return {
                    "error": project_data["error"],
                    "project_id": project_id
                }

            # Extract outline from milestones
            milestones = project_data.get("milestones", {})
            outline_milestone = milestones.get("outline_generated")

            if not outline_milestone:
                return {
                    "error": "No outline found for this project. Generate one first using generate_outline.",
                    "project_id": project_id,
                    "has_outline": False
                }

            outline = outline_milestone.get("data", {}).get("outline", {})

            logger.info(f"Successfully retrieved outline for project {project_id}")
            return {
                "project_id": project_id,
                "outline": outline,
                "outline_title": outline.get("title", "Unknown"),
                "has_outline": True,
                "total_sections": len(outline.get("sections", []))
            }

    except Exception as e:
        logger.error(f"Error during outline retrieval: {e}")
        return {
            "error": f"Failed to retrieve outline: {str(e)}",
            "project_id": project_id
        }


@mcp.tool()
async def regenerate_outline(
    project_id: str,
    user_guidelines: str
) -> Dict[str, Any]:
    """
    Regenerate the blog outline with new guidelines.

    This tool regenerates the outline for a project using new user guidelines.
    It's useful when you want to adjust the outline structure or focus based on feedback.

    Args:
        project_id: The unique identifier for the project.
        user_guidelines: New guidelines or instructions for outline regeneration.
                        Required. Examples:
                        - "Add more technical depth to the sections"
                        - "Reorganize to follow a tutorial structure"
                        - "Focus on real-world applications"

    Returns:
        A dictionary containing:
        - project_id: The project identifier
        - outline: The newly generated outline with sections
        - outline_hash: Hash of the new outline
        - was_cached: Whether the outline was retrieved from cache (usually False for regeneration)

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await regenerate_outline(
            project_id="abc123",
            user_guidelines="Add more code examples and make it beginner-friendly"
        )
    """
    if not user_guidelines:
        return {
            "error": "user_guidelines parameter is required for regeneration",
            "project_id": project_id
        }

    try:
        async with BackendAPIClient() as client:
            # Regenerate outline with new guidelines
            # The existing generate_outline method will regenerate the outline
            result = await client.generate_outline(
                project_id=project_id,
                user_guidelines=user_guidelines
            )

            logger.info(f"Successfully regenerated outline for project {project_id}")
            return result

    except Exception as e:
        logger.error(f"Error during outline regeneration: {e}")
        return {
            "error": f"Failed to regenerate outline: {str(e)}",
            "project_id": project_id
        }
