# ABOUTME: Main MCP server entry point
# ABOUTME: Runs the FastMCP server with all registered tools

import logging
import sys

# Configure logging to stderr (important for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


def main():
    """
    Run the MCP server with all registered tools.

    Each tool module creates its own FastMCP instance, but FastMCP
    is designed to run each instance separately. We need to import
    all tool modules so they're available, then run the server.
    """
    logger.info("Starting Agentic Blogging Assistant MCP Server...")

    try:
        # Import all tool modules to ensure they're loaded
        # This makes the tools available even though we're not explicitly using them here
        import mcp_server.tools.project_tools
        import mcp_server.tools.file_tools
        import mcp_server.tools.outline_tools
        import mcp_server.tools.section_tools
        import mcp_server.tools.refine_tools
        import mcp_server.tools.automation_tool

        logger.info("All tool modules imported successfully")

        # Get the first FastMCP instance and run it
        # Note: In FastMCP, each instance is separate, so we'll run project_tools
        from mcp_server.tools.project_tools import mcp

        logger.info("Starting MCP server...")
        mcp.run()

    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
