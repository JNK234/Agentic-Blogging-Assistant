# MCP Server Structure

## Directory Layout

```
root/mcp_server/
├── __init__.py                 # Package initialization
├── server.py                   # Main entry point - registers all tools
├── api_client.py               # Backend API client
├── config.py                   # Configuration settings
├── requirements-mcp.txt        # Dependencies
├── README.md                   # Documentation
├── .env.example                # Environment variable template
├── tools/                      # MCP tool implementations
│   ├── __init__.py            # Exports all tool functions
│   ├── project_tools.py       # Project management (4 tools)
│   ├── file_tools.py          # File upload/processing (2 tools)
│   ├── outline_tools.py       # Outline generation (3 tools)
│   ├── section_tools.py       # Section drafting (4 tools)
│   ├── refine_tools.py        # Refinement & titles (2 tools)
│   └── automation_tool.py     # Complete automation (1 tool)
└── utils/                      # Utility modules
    ├── __init__.py
    └── file_handler.py        # File encoding/decoding utilities
```

## Tool Inventory (17 Total)

### Project Management Tools (4)
- `create_project` - Create a new blogging project
- `list_projects` - List all projects
- `get_project_status` - Get detailed project status
- `delete_project` - Delete a project

### File Tools (2)
- `upload_files` - Upload files to a project
- `process_files` - Process uploaded files for content extraction

### Outline Tools (3)
- `generate_outline` - Generate blog outline from processed content
- `get_outline` - Retrieve existing outline
- `regenerate_outline` - Regenerate outline with feedback

### Section Tools (4)
- `draft_section` - Draft a specific section
- `get_section` - Retrieve a drafted section
- `regenerate_section` - Regenerate section with feedback
- `get_all_sections` - Get all sections for a project

### Refinement Tools (2)
- `refine_section` - Refine a section with focused feedback
- `generate_title_options` - Generate title options for the blog

### Automation Tool (1)
- `generate_complete_blog` - End-to-end blog generation

## Running the Server

```bash
# Install dependencies
cd root/mcp_server
pip install -r requirements-mcp.txt

# Run the server
python server.py
```

The server will:
1. Import all 6 tool modules
2. Register all 17 tools with the main MCP instance
3. Start the FastMCP server on the default port
4. Log registration progress for each module

## Key Files

- **server.py**: Main entry point with `if __name__ == "__main__": mcp.run()`
- **tools/__init__.py**: Exports all tool functions for easy importing
- **requirements-mcp.txt**: All dependencies with minimum versions
- **utils/__init__.py**: Empty placeholder for future utilities
