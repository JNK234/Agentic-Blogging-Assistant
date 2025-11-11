# Claude Desktop Setup Guide for MCP Server

## Prerequisites

✅ Python 3.11+ installed
✅ FastMCP and dependencies installed (`pip install -r requirements-mcp.txt`)
✅ Backend server running on `http://localhost:8000`
✅ Claude Desktop application installed

## Configuration Steps

### 1. Locate Claude Desktop Config File

**macOS**: `~/.claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/claude/claude_desktop_config.json`

### 2. Add MCP Server Configuration

Edit the `claude_desktop_config.json` file and add the following:

```json
{
  "mcpServers": {
    "agentic-blogging-assistant": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "BACKEND_URL": "http://localhost:8000",
        "MCP_SERVER_NAME": "agentic-blogging-assistant",
        "LOG_LEVEL": "INFO",
        "PYTHONPATH": "/Users/jnk789/Developer/Agentic Blogging Assistant/Agentic-Blogging-Assistant/root"
      }
    }
  }
}
```

**IMPORTANT**: Replace the `PYTHONPATH` value with your actual project root path.

### 3. Restart Claude Desktop

After saving the configuration:
1. Quit Claude Desktop completely
2. Relaunch Claude Desktop
3. The MCP server will automatically start when Claude Desktop launches

### 4. Verify Connection

In Claude Desktop, you should see the MCP server tools available:

**Project Management** (4 tools):
- `create_project` - Create a new blog project
- `list_projects` - List all projects
- `get_project_status` - Get project details and status
- `delete_project` - Delete a project

**File Operations** (2 tools):
- `upload_files` - Upload files to a project
- `process_files` - Process uploaded files

**Outline Management** (3 tools):
- `generate_outline` - Generate blog outline
- `get_outline` - Retrieve existing outline
- `regenerate_outline` - Regenerate outline with new guidelines

**Section Drafting** (4 tools):
- `draft_section` - Draft a specific section
- `get_section` - Retrieve section content
- `regenerate_section` - Regenerate section with feedback
- `get_all_sections` - Get all sections

**Refinement** (2 tools):
- `refine_section` - Refine a specific section
- `generate_title_options` - Generate title alternatives

**Automation** (1 tool):
- `generate_complete_blog` - End-to-end blog generation

## Testing the Setup

Try these commands in Claude Desktop:

### Test 1: List Projects
```
List all my blog projects
```

### Test 2: Create Project
```
Create a new blog project named "Test Blog" with Tech Blog Writer persona
```

### Test 3: Complete Automation
```
Generate a complete blog from my notebook file about machine learning
```

## Troubleshooting

### MCP Server Not Showing Up

1. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`

2. Verify PYTHONPATH is correct:
   ```bash
   python -c "import sys; sys.path.append('/path/to/your/root'); from mcp_server import server; print('OK')"
   ```

3. Test MCP server manually:
   ```bash
   cd /path/to/Agentic-Blogging-Assistant/root
   python -m mcp_server.server
   ```

### Backend Connection Issues

1. Verify backend is running:
   ```bash
   curl http://localhost:8000/health
   ```

2. Check backend URL in environment:
   ```bash
   echo $BACKEND_URL
   ```

3. Update `BACKEND_URL` in config if using different port

### Tool Execution Errors

1. Check backend logs for API errors
2. Verify project_id exists before operating on it
3. Ensure files are uploaded before processing
4. Check that outline exists before drafting sections

## Environment Variables

You can customize these in the `env` section of the config:

- `BACKEND_URL`: Backend API URL (default: `http://localhost:8000`)
- `MCP_SERVER_NAME`: Server name (default: `agentic-blogging-assistant`)
- `LOG_LEVEL`: Logging level (default: `INFO`, options: `DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `PYTHONPATH`: Python module search path (required)

## Advanced Configuration

### Using Custom Backend Port

```json
"env": {
  "BACKEND_URL": "http://localhost:9000",
  ...
}
```

### Debug Mode

```json
"env": {
  "LOG_LEVEL": "DEBUG",
  ...
}
```

### Multiple Environments

Create separate MCP server entries for dev/prod:

```json
{
  "mcpServers": {
    "blog-assistant-dev": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "BACKEND_URL": "http://localhost:8000",
        ...
      }
    },
    "blog-assistant-prod": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "BACKEND_URL": "https://api.yourdomain.com",
        ...
      }
    }
  }
}
```

## Support

For issues:
1. Check the logs in `~/.claude/logs/`
2. Verify all prerequisites are met
3. Test the MCP server standalone before connecting to Claude Desktop
4. Ensure the backend API is accessible
