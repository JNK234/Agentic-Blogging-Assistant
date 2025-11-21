# ABOUTME: Test script to verify all MCP tools are properly registered
# ABOUTME: Run with: python -m mcp_server.test_tools

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.tools import (
    project_tools,
    file_tools,
    outline_tools,
    section_tools,
    refine_tools,
    automation_tool
)


async def main():
    """Test all MCP tool registrations."""
    print("=" * 60)
    print("MCP Server Tool Registration Test")
    print("=" * 60)

    tool_modules = [
        ("Project Tools", project_tools.mcp),
        ("File Tools", file_tools.mcp),
        ("Outline Tools", outline_tools.mcp),
        ("Section Tools", section_tools.mcp),
        ("Refine Tools", refine_tools.mcp),
        ("Automation Tools", automation_tool.mcp),
    ]

    total_tools = 0
    for name, mcp_instance in tool_modules:
        tools = await mcp_instance.list_tools()
        tool_count = len(tools)
        total_tools += tool_count
        print(f"\n✓ {name}: {tool_count} tools")
        for tool in tools:
            tool_name = tool.name if hasattr(tool, 'name') else str(tool)
            print(f"  - {tool_name}")

    print(f"\n{'=' * 60}")
    print(f"✓ Total Tools Registered: {total_tools}")
    print(f"{'=' * 60}\n")

    return total_tools


if __name__ == "__main__":
    result = asyncio.run(main())
    if result >= 16:  # Expecting at least 16 tools
        print("✅ All tools registered successfully!")
        sys.exit(0)
    else:
        print(f"❌ Expected at least 16 tools, got {result}")
        sys.exit(1)
