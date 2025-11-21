# ABOUTME: FastMCP tools for project management operations (create, list, get, delete)
# ABOUTME: Provides MCP interface to backend project management API endpoints

from typing import Optional, Dict, Any
import logging
from mcp.server.fastmcp import FastMCP

from ..api_client import BackendAPIClient

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("project-tools")


@mcp.tool()
async def create_project(
    name: str,
    persona: str = "Tech Blog Writer",
    model: str = "gpt-4o-mini",
    specific_model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new blogging project.

    This initializes a new project in the blogging assistant system with the specified
    configuration. The project can then be used to upload files, generate outlines,
    and create blog drafts.

    Args:
        name: Name for the new project (e.g., "My ML Tutorial Blog")
        persona: Writing persona to use (default: "Tech Blog Writer")
                 Options: "Tech Blog Writer", "Academic Researcher", "Tutorial Creator"
        model: Base model to use for content generation (default: "gpt-4o-mini")
               Options: "gpt-4o-mini", "gpt-4o", "claude-3-5-sonnet-20241022", "deepseek-chat"
        specific_model: Specific model identifier if using a custom/fine-tuned model (optional)

    Returns:
        Dictionary containing:
        - message: Success message
        - project_name: Name of the created project
        - project_id: UUID of the created project
        - files: List of uploaded files (minimal init file)

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await create_project(
            "ML Tutorial Series",
            persona="Tutorial Creator",
            model="gpt-4o"
        )
        print(f"Created project: {result['project_id']}")
    """
    try:
        logger.info(f"Creating project: {name}")
        async with BackendAPIClient() as client:
            metadata = {
                "model_name": model,
                "persona": persona
            }
            if specific_model:
                metadata["specific_model"] = specific_model

            result = await client.create_project(
                name=name,
                metadata=metadata
            )
            logger.info(f"Successfully created project: {result.get('project_id')}")
            return result
    except ConnectionError as e:
        logger.error(f"Connection error creating project: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating project: {e}")
        raise ValueError(f"Failed to create project: {str(e)}")


@mcp.tool()
async def list_projects(status: Optional[str] = None) -> Dict[str, Any]:
    """
    List all projects with optional status filter.

    Retrieves a list of all projects in the system, optionally filtered by their
    current status. Useful for finding existing projects or checking project states.

    Args:
        status: Optional status filter
                - "active": Only active projects
                - "archived": Only archived projects
                - None: All projects (default)

    Returns:
        Dictionary containing:
        - status: API response status
        - count: Number of projects returned
        - projects: List of project dictionaries with metadata

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await list_projects(status="active")
        for project in result['projects']:
            print(f"{project['name']}: {project['current_milestone']}")
    """
    try:
        logger.info(f"Listing projects with status: {status or 'all'}")
        async with BackendAPIClient() as client:
            result = await client.list_projects(status=status)
            logger.info(f"Found {result.get('count', 0)} projects")
            return result
    except ConnectionError as e:
        logger.error(f"Connection error listing projects: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing projects: {e}")
        raise ValueError(f"Failed to list projects: {str(e)}")


@mcp.tool()
async def get_project_status(project_id: str) -> Dict[str, Any]:
    """
    Get detailed status and information for a specific project.

    Retrieves comprehensive information about a project including its current milestone,
    metadata, configuration, and progress through the blogging workflow.

    Args:
        project_id: UUID of the project to query

    Returns:
        Dictionary containing:
        - status: API response status
        - project: Project metadata (name, status, creation date, etc.)
        - milestones: Dictionary of completed milestones with their data

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await get_project_status("123e4567-e89b-12d3-a456-426614174000")
        print(f"Project: {result['project']['name']}")
        print(f"Status: {result['project']['status']}")
        print(f"Milestones: {list(result['milestones'].keys())}")
    """
    try:
        logger.info(f"Getting status for project: {project_id}")
        async with BackendAPIClient() as client:
            result = await client.get_project(project_id)
            logger.info(f"Successfully retrieved project status")
            return result
    except ConnectionError as e:
        logger.error(f"Connection error getting project status: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting project status: {e}")
        raise ValueError(f"Failed to get project status: {str(e)}")


@mcp.tool()
async def delete_project(project_id: str) -> Dict[str, Any]:
    """
    Permanently delete a project and all its associated data.

    This operation cannot be undone. All project data including uploaded files,
    outlines, drafts, and milestones will be permanently removed from the system.

    Use with caution - consider archiving instead if you might need the project later.

    Args:
        project_id: UUID of the project to delete

    Returns:
        Dictionary containing:
        - status: Operation status
        - message: Confirmation message

    Raises:
        ConnectionError: If unable to connect to the backend API
        ValueError: If the API returns an invalid response

    Example:
        result = await delete_project("123e4567-e89b-12d3-a456-426614174000")
        print(result['message'])
    """
    try:
        logger.info(f"Deleting project: {project_id}")
        async with BackendAPIClient() as client:
            result = await client.delete_project(project_id)
            logger.info(f"Successfully deleted project")
            return result
    except ConnectionError as e:
        logger.error(f"Connection error deleting project: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting project: {e}")
        raise ValueError(f"Failed to delete project: {str(e)}")
