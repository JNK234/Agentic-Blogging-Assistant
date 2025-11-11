# Agentic Blogging Assistant MCP Server

Transform your technical content into polished blog posts using AI-powered tools through the Model Context Protocol (MCP). This MCP server exposes 16 specialized tools that integrate seamlessly with Claude Desktop and other MCP-compatible AI assistants.

## Overview

The Agentic Blogging Assistant MCP Server provides a complete workflow for converting Jupyter notebooks, Markdown files, and Python code into publication-ready blog posts. Whether you want full automation or fine-grained control over each step, these tools have you covered.

**Key Capabilities**:
- Create and manage blogging projects
- Upload and process technical content (.ipynb, .md, .py)
- Generate structured blog outlines
- Draft individual sections with quality control
- Refine content with targeted feedback
- Full end-to-end automation option
- Track costs across all operations

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Backend API running on `http://localhost:8000`
- Claude Desktop (for Claude integration)

### Installation

1. Install MCP server dependencies:
```bash
cd root/mcp_server
pip install -r requirements-mcp.txt
```

2. Start the backend API (in a separate terminal):
```bash
cd root/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

3. Configure Claude Desktop (see [Claude Desktop Integration](#claude-desktop-integration))

### Test Your Installation

```bash
cd root/mcp_server
python test_tools.py
```

Expected output: `✅ All tools registered successfully!` with 16 tools listed.

## Available Tools (16 Total)

### Project Management (4 tools)

**1. `create_project`** - Initialize a new blog project
```python
# Example usage in Claude Desktop:
"Create a new blog project called 'ML Tutorial Series' using the Tech Blog Writer persona"

# Returns: project_id for use in subsequent operations
```

**2. `list_projects`** - List all projects with optional status filter
```python
"Show me all my active blog projects"
```

**3. `get_project_status`** - Get detailed project information
```python
"What's the status of project abc-123?"
```

**4. `delete_project`** - Permanently delete a project
```python
"Delete the test project I created earlier"
```

### File Operations (2 tools)

**5. `upload_files`** - Upload files to a project (base64-encoded)
```python
# Supports .ipynb, .md, .py files
"Upload my notebook tutorial.ipynb to the ML project"
```

**6. `process_files`** - Extract content and create embeddings
```python
# Processes uploaded files for use in outline/blog generation
"Process all the files I just uploaded using GPT-4o"
```

### Outline Management (3 tools)

**7. `generate_outline`** - Generate structured blog outline
```python
"Generate an outline for my ML project focusing on practical examples"
```

**8. `get_outline`** - Retrieve existing outline
```python
"Show me the outline for project abc-123"
```

**9. `regenerate_outline`** - Regenerate with new guidelines
```python
"Regenerate the outline but make it more beginner-friendly"
```

### Section Drafting (4 tools)

**10. `draft_section`** - Generate a specific section with quality control
```python
# Includes iterative refinement based on quality scoring
"Draft section 0 with quality threshold 0.85"
```

**11. `get_section`** - Retrieve a drafted section
```python
"Show me section 2 of the blog"
```

**12. `regenerate_section`** - Regenerate section with feedback
```python
"Regenerate section 1 with more code examples"
```

**13. `get_all_sections`** - Retrieve all drafted sections
```python
"Show me all the sections that have been drafted"
```

### Refinement (2 tools)

**14. `refine_section`** - Improve a section with targeted feedback
```python
# Focus options: overall, clarity, technical, concise, engaging, examples
"Refine section 0 for better clarity"
"Refine section 2 to add more technical depth"
```

**15. `generate_title_options`** - Generate alternative titles
```python
"Give me 5 catchy title options for this blog"
```

### Automation (1 tool)

**16. `generate_complete_blog`** - Full end-to-end blog generation
```python
# Orchestrates: project creation → file upload → processing →
#               outline → drafting → refinement → export
"Generate a complete blog from my notebooks about RAG systems"
```

## Architecture

```
mcp_server/
├── server.py                    # Main MCP server entry point
├── api_client.py               # Backend API client
├── config.py                   # Configuration settings
├── requirements-mcp.txt        # MCP server dependencies
├── test_tools.py               # Tool registration test
├── tools/                      # 16 MCP tools organized by category
│   ├── __init__.py
│   ├── project_tools.py       # Project management (4 tools)
│   ├── file_tools.py          # File operations (2 tools)
│   ├── outline_tools.py       # Outline management (3 tools)
│   ├── section_tools.py       # Section drafting (4 tools)
│   ├── refine_tools.py        # Refinement (2 tools)
│   └── automation_tool.py     # Complete automation (1 tool)
└── utils/                      # Utilities
    ├── __init__.py
    └── file_handler.py        # File encoding/decoding
```

## Claude Desktop Integration

### Setup Steps

1. Locate your Claude Desktop config file:
   - **macOS**: `~/.claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/claude/claude_desktop_config.json`

2. Add the MCP server configuration:
```json
{
  "mcpServers": {
    "agentic-blogging-assistant": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "BACKEND_URL": "http://localhost:8000",
        "MCP_SERVER_NAME": "agentic-blogging-assistant",
        "LOG_LEVEL": "INFO",
        "PYTHONPATH": "/path/to/Agentic-Blogging-Assistant/root"
      }
    }
  }
}
```

**Important**: Replace `/path/to/Agentic-Blogging-Assistant/root` with your actual project path.

3. Restart Claude Desktop completely (quit and relaunch)

4. Verify the tools appear in Claude Desktop's tool list

See [CLAUDE_DESKTOP_SETUP.md](./CLAUDE_DESKTOP_SETUP.md) for detailed setup instructions and troubleshooting.

## Usage Examples

### Conversational Workflow with Claude Desktop

**Automated Approach** (using `generate_complete_blog`):
```
You: "I have a Jupyter notebook about building RAG systems.
     Can you turn it into a blog post?"

Claude: "I'll use the generate_complete_blog tool to create a
        complete blog post. What would you like to name this project?"

You: "Call it 'Building RAG Systems with LangChain'"

Claude: [Uses generate_complete_blog tool]
        "Great! I've generated your blog post. It has 5 sections:
        - Introduction to RAG
        - Setting Up Your Environment
        - Implementation Details
        - Testing and Validation
        - Conclusion

        Total cost: $0.15
        Would you like me to refine any sections?"
```

**Iterative Approach** (step-by-step control):
```
You: "Create a new blog project called 'PyTorch Tutorial'"

Claude: [Uses create_project]
        "Project created! ID: abc-123-def"

You: "Upload my notebook pytorch_basics.ipynb"

Claude: [Uses upload_files]
        "File uploaded successfully"

You: "Process the files and generate an outline"

Claude: [Uses process_files, then generate_outline]
        "Here's your outline:
        1. Introduction to PyTorch
        2. Tensors and Operations
        3. Building Neural Networks
        4. Training Your First Model
        5. Conclusion

        Would you like to proceed with drafting?"

You: "Draft section 2 with high quality"

Claude: [Uses draft_section with quality_threshold=0.85]
        "Section 2 drafted! Quality score: 0.87
        Here's the content..."

You: "Make it more concise"

Claude: [Uses refine_section with focus='concise']
        "Refined section 2 for conciseness. Better?"
```

### Cost Tracking

Every operation tracks costs automatically:

```python
# Individual operation costs
{
  "section_cost": 0.02,
  "section_tokens": 1500
}

# Project-level cost summary
{
  "total_cost": 0.15,
  "total_tokens": 12000,
  "agent_breakdown": {
    "content_parsing": {"cost": 0.03, "tokens": 2000},
    "outline_generation": {"cost": 0.04, "tokens": 3000},
    "blog_drafting": {"cost": 0.08, "tokens": 7000}
  }
}
```

## Workflow Patterns

### Pattern 1: Quick Blog Generation
Best for: Fast content creation with minimal customization

```
1. generate_complete_blog(
     project_name="My Tutorial",
     files=["/path/to/notebook.ipynb"],
     auto_refine=True
   )
```

### Pattern 2: Controlled Iteration
Best for: High-quality output with manual review at each step

```
1. create_project() → get project_id
2. upload_files() → upload content
3. process_files() → extract and embed content
4. generate_outline() → review structure
5. regenerate_outline() → adjust if needed
6. For each section:
   - draft_section() → generate content
   - refine_section() → improve quality
   - get_section() → review
7. generate_title_options() → pick best title
```

### Pattern 3: Hybrid Approach
Best for: Balance between speed and control

```
1. generate_complete_blog(auto_refine=False) → fast initial draft
2. Review generated sections
3. refine_section() → improve specific sections that need work
4. generate_title_options() → optimize title
```

## Configuration

### Environment Variables

Set these in your Claude Desktop config or `.env` file:

- `BACKEND_URL`: Backend API URL (default: `http://localhost:8000`)
- `MCP_SERVER_NAME`: Server name (default: `agentic-blogging-assistant`)
- `LOG_LEVEL`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Model Selection

Most tools support multiple LLM providers:
- `gpt-4o-mini` (default, cost-effective)
- `gpt-4o` (highest quality OpenAI)
- `claude-3-5-sonnet-20241022` (Anthropic)
- `deepseek-chat` (DeepSeek)
- `gemini-2.0-flash-exp` (Google)

Specify in `create_project()` or individual tool calls.

## Development

### Running the Server Standalone

```bash
cd root/mcp_server
python -m mcp_server.server
```

### Adding New Tools

1. Choose the appropriate category file in `tools/`
2. Define your tool function:
```python
@mcp.tool()
async def my_new_tool(param1: str, param2: int = 5) -> Dict[str, Any]:
    """
    Tool description that Claude will see.

    Args:
        param1: Description
        param2: Description with default

    Returns:
        Dictionary with results
    """
    async with BackendAPIClient() as client:
        result = await client.my_backend_method()
        return result
```

3. Test with `python test_tools.py`

### Backend API Client

The `BackendAPIClient` provides async HTTP interface to the FastAPI backend:

```python
from mcp_server.api_client import BackendAPIClient

async with BackendAPIClient(base_url="http://localhost:8000") as client:
    projects = await client.list_projects()
    outline = await client.generate_outline(project_id, guidelines)
```

## Error Handling

All tools provide structured error responses:

```python
# Success response
{
  "status": "success",
  "data": {...}
}

# Error response
{
  "error": "Detailed error message",
  "project_id": "abc-123",  # Context when available
  "status_code": 404
}
```

Common errors:
- `ConnectionError`: Backend API unavailable
- `ValueError`: Invalid parameters or missing data
- `FileNotFoundError`: Specified files don't exist

## Troubleshooting

### MCP Server Not Appearing in Claude Desktop

1. Check Claude Desktop logs: `~/Library/Logs/Claude/` (macOS)
2. Verify PYTHONPATH in config points to correct root directory
3. Test server standalone: `python -m mcp_server.server`
4. Ensure backend is running: `curl http://localhost:8000/health`

### Tool Execution Failures

1. Verify workflow order:
   - Create project before uploading files
   - Process files before generating outline
   - Generate outline before drafting sections

2. Check backend logs for detailed errors

3. Validate project_id exists: use `get_project_status()`

### Performance Issues

1. Use `gpt-4o-mini` for faster/cheaper operations
2. Reduce `max_iterations` in `draft_section()`
3. Set `auto_refine=False` in `generate_complete_blog()`
4. Process fewer files at once

## Testing

Run the comprehensive test suite:

```bash
cd root/mcp_server
python test_tools.py
```

Expected output:
```
============================================================
MCP Server Tool Registration Test
============================================================

✓ Project Tools: 4 tools
  - create_project
  - list_projects
  - get_project_status
  - delete_project

✓ File Tools: 2 tools
  - upload_files
  - process_files

✓ Outline Tools: 3 tools
  - generate_outline
  - get_outline
  - regenerate_outline

✓ Section Tools: 4 tools
  - draft_section
  - get_section
  - regenerate_section
  - get_all_sections

✓ Refine Tools: 2 tools
  - refine_section
  - generate_title_options

✓ Automation Tools: 1 tool
  - generate_complete_blog

============================================================
✓ Total Tools Registered: 16
============================================================

✅ All tools registered successfully!
```

## Documentation

- [CLAUDE_DESKTOP_SETUP.md](./CLAUDE_DESKTOP_SETUP.md) - Detailed Claude Desktop integration guide
- [STRUCTURE.md](./STRUCTURE.md) - Architecture and design decisions
- Backend API: `http://localhost:8000/docs` - Interactive API documentation

## Support

For issues or questions:
1. Check the logs: `~/.claude/logs/` (Claude Desktop) or console output (standalone)
2. Verify backend is running: `curl http://localhost:8000/health`
3. Test tools individually with `python test_tools.py`
4. Review backend API docs: `http://localhost:8000/docs`

## License

Part of the Agentic Blogging Assistant project.
