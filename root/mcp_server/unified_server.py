# ABOUTME: Unified MCP server with all tools registered on a single FastMCP instance
# ABOUTME: This is the correct entry point for Claude Desktop

import logging
import sys
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP

from mcp_server.api_client import BackendAPIClient

# Configure logging to stderr (MCP requirement)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Create a single unified FastMCP server
mcp = FastMCP("agentic-blogging-assistant")


# ============================================================================
# PROJECT TOOLS
# ============================================================================

@mcp.tool()
async def create_project(
    name: str,
    persona: str = "Tech Blog Writer",
    model: str = "gpt-4o-mini",
    guidelines: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new blog project with specified persona and model.

    Args:
        name: Project name
        persona: Writing persona (Tech Blog Writer, Academic Researcher, Tutorial Creator)
        model: LLM model to use (gpt-4o-mini, gpt-4o, claude-3-5-sonnet-20241022, etc.)
        guidelines: Optional user guidelines for content generation

    Returns:
        Dictionary with project_id and status
    """
    async with BackendAPIClient() as client:
        return await client.create_project(name, persona, model, guidelines)


@mcp.tool()
async def list_projects(status: Optional[str] = None) -> Dict[str, Any]:
    """
    List all blog projects with optional status filtering.

    Args:
        status: Optional status filter (active, completed, archived)

    Returns:
        Dictionary with list of projects
    """
    async with BackendAPIClient() as client:
        return await client.list_projects(status)


@mcp.tool()
async def get_project_status(project_id: str) -> Dict[str, Any]:
    """
    Get detailed status and information for a specific project.

    Args:
        project_id: The project ID to retrieve

    Returns:
        Dictionary with project details, milestones, and costs
    """
    async with BackendAPIClient() as client:
        return await client.get_project_status(project_id)


@mcp.tool()
async def delete_project(project_id: str) -> Dict[str, Any]:
    """
    Permanently delete a project and all its data.

    Args:
        project_id: The project ID to delete

    Returns:
        Dictionary with deletion confirmation
    """
    async with BackendAPIClient() as client:
        return await client.delete_project(project_id)


# ============================================================================
# FILE TOOLS
# ============================================================================

@mcp.tool()
async def upload_files(project_id: str, files: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Upload files to a project for processing.

    Args:
        project_id: The project to upload files to
        files: List of dicts with 'filename' and 'content' (base64 encoded)

    Returns:
        Dictionary with upload status
    """
    async with BackendAPIClient() as client:
        return await client.upload_files(project_id, files)


@mcp.tool()
async def process_files(project_id: str) -> Dict[str, Any]:
    """
    Process uploaded files to extract content and create embeddings.

    Args:
        project_id: The project whose files should be processed

    Returns:
        Dictionary with processing results
    """
    async with BackendAPIClient() as client:
        return await client.process_files(project_id)


# ============================================================================
# OUTLINE TOOLS
# ============================================================================

@mcp.tool()
async def generate_outline(
    project_id: str,
    guidelines: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a structured blog outline from processed content.

    Args:
        project_id: The project to generate outline for
        guidelines: Optional additional guidelines for outline generation

    Returns:
        Dictionary with generated outline
    """
    async with BackendAPIClient() as client:
        return await client.generate_outline(project_id, guidelines)


@mcp.tool()
async def get_outline(project_id: str) -> Dict[str, Any]:
    """
    Retrieve the existing outline for a project.

    Args:
        project_id: The project ID

    Returns:
        Dictionary with outline data
    """
    async with BackendAPIClient() as client:
        return await client.get_outline(project_id)


@mcp.tool()
async def regenerate_outline(
    project_id: str,
    feedback: str,
    guidelines: Optional[str] = None
) -> Dict[str, Any]:
    """
    Regenerate outline with user feedback.

    Args:
        project_id: The project ID
        feedback: User feedback for outline regeneration
        guidelines: Optional updated guidelines

    Returns:
        Dictionary with regenerated outline
    """
    async with BackendAPIClient() as client:
        return await client.regenerate_outline(project_id, feedback, guidelines)


# ============================================================================
# SECTION TOOLS
# ============================================================================

@mcp.tool()
async def draft_section(project_id: str, section_index: int) -> Dict[str, Any]:
    """
    Draft a specific section of the blog.

    Args:
        project_id: The project ID
        section_index: Zero-based index of section to draft

    Returns:
        Dictionary with drafted section content and quality metrics
    """
    async with BackendAPIClient() as client:
        return await client.draft_section(project_id, section_index)


@mcp.tool()
async def get_section(project_id: str, section_index: int) -> Dict[str, Any]:
    """
    Retrieve a specific drafted section.

    Args:
        project_id: The project ID
        section_index: Zero-based index of section to retrieve

    Returns:
        Dictionary with section content
    """
    async with BackendAPIClient() as client:
        return await client.get_section(project_id, section_index)


@mcp.tool()
async def regenerate_section(
    project_id: str,
    section_index: int,
    feedback: str
) -> Dict[str, Any]:
    """
    Regenerate a section with user feedback.

    Args:
        project_id: The project ID
        section_index: Zero-based index of section to regenerate
        feedback: User feedback for improvement

    Returns:
        Dictionary with regenerated section
    """
    async with BackendAPIClient() as client:
        return await client.regenerate_section(project_id, section_index, feedback)


@mcp.tool()
async def get_all_sections(project_id: str) -> Dict[str, Any]:
    """
    Retrieve all drafted sections for a project.

    Args:
        project_id: The project ID

    Returns:
        Dictionary with all sections
    """
    async with BackendAPIClient() as client:
        return await client.get_all_sections(project_id)


# ============================================================================
# REFINEMENT TOOLS
# ============================================================================

@mcp.tool()
async def refine_section(
    project_id: str,
    section_index: int,
    focus: str = "clarity"
) -> Dict[str, Any]:
    """
    Refine a section with specific focus areas.

    Args:
        project_id: The project ID
        section_index: Zero-based index of section to refine
        focus: Focus area (clarity, technical_depth, conciseness, engagement, code_examples)

    Returns:
        Dictionary with refined section
    """
    async with BackendAPIClient() as client:
        return await client.refine_section(project_id, section_index, focus)


@mcp.tool()
async def generate_title_options(project_id: str) -> Dict[str, Any]:
    """
    Generate alternative title options for the blog.

    Args:
        project_id: The project ID

    Returns:
        Dictionary with 5 title options and rationales
    """
    async with BackendAPIClient() as client:
        return await client.generate_title_options(project_id)


# ============================================================================
# AUTOMATION TOOL
# ============================================================================

@mcp.tool()
async def generate_complete_blog(
    project_name: str,
    file_path: str,
    persona: str = "Tech Blog Writer",
    model: str = "gpt-4o-mini",
    guidelines: Optional[str] = None
) -> Dict[str, Any]:
    """
    End-to-end blog generation from file upload to complete draft.

    This tool orchestrates the entire workflow:
    1. Creates project
    2. Uploads and processes files
    3. Generates outline
    4. Drafts all sections
    5. Refines content
    6. Generates title options

    Args:
        project_name: Name for the new project
        file_path: Path to notebook or markdown file
        persona: Writing persona to use
        model: LLM model to use
        guidelines: Optional user guidelines

    Returns:
        Dictionary with complete blog including all sections and metadata
    """
    async with BackendAPIClient() as client:
        return await client.generate_complete_blog(
            project_name, file_path, persona, model, guidelines
        )


def main():
    """Run the unified MCP server."""
    logger.info("Starting Agentic Blogging Assistant MCP Server (Unified)...")
    logger.info("Registered 16 tools across 6 categories")
    mcp.run()


if __name__ == "__main__":
    main()
