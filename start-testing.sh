#!/bin/bash
# ABOUTME: Startup script for testing the Agentic Blogging Assistant MCP server
# ABOUTME: Starts both backend and provides instructions for Claude Desktop testing

set -e  # Exit on error

PROJECT_ROOT="/Users/jnk789/Developer/Agentic Blogging Assistant/Agentic-Blogging-Assistant"
BACKEND_DIR="$PROJECT_ROOT/root/backend"
MCP_SERVER_DIR="$PROJECT_ROOT/root/mcp_server"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Agentic Blogging Assistant MCP Server Testing Setup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Step 1: Check dependencies
echo -e "${YELLOW}[1/5] Checking dependencies...${NC}"
cd "$PROJECT_ROOT/root"

if ! python3 -c "import mcp; import aiohttp; import pydantic; import dotenv" 2>/dev/null; then
    echo -e "${RED}❌ MCP dependencies missing. Installing...${NC}"
    pip install -r "$MCP_SERVER_DIR/requirements-mcp.txt"
fi

if ! python3 -c "import fastapi; import uvicorn" 2>/dev/null; then
    echo -e "${RED}❌ Backend dependencies missing. Installing...${NC}"
    pip install -r requirements.txt
fi

echo -e "${GREEN}✅ All dependencies installed${NC}"
echo ""

# Step 2: Test MCP server tool registration
echo -e "${YELLOW}[2/5] Testing MCP server tool registration...${NC}"
cd "$MCP_SERVER_DIR"
python3 test_tools.py
echo ""

# Step 3: Check if backend is already running
echo -e "${YELLOW}[3/5] Checking backend server...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend already running on port 8000${NC}"
    BACKEND_RUNNING=true
else
    echo -e "${YELLOW}⚠️  Backend not running. Starting backend server...${NC}"
    cd "$BACKEND_DIR"

    # Start backend in background
    nohup uvicorn main:app --reload --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > /tmp/backend.pid

    # Wait for backend to start
    echo -n "Waiting for backend to start"
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✅ Backend started successfully (PID: $BACKEND_PID)${NC}"
            BACKEND_RUNNING=true
            break
        fi
        echo -n "."
        sleep 1
    done

    if [ "$BACKEND_RUNNING" != true ]; then
        echo ""
        echo -e "${RED}❌ Failed to start backend. Check logs: tail -f /tmp/backend.log${NC}"
        exit 1
    fi
fi
echo ""

# Step 4: Generate Claude Desktop config
echo -e "${YELLOW}[4/5] Generating Claude Desktop configuration...${NC}"

CLAUDE_CONFIG_DIR="$HOME/.claude"
CLAUDE_CONFIG_FILE="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

# Create config directory if it doesn't exist
mkdir -p "$CLAUDE_CONFIG_DIR"

# Check if config already exists
if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    echo -e "${YELLOW}⚠️  Claude Desktop config already exists${NC}"
    echo -e "Location: ${BLUE}$CLAUDE_CONFIG_FILE${NC}"
    echo ""
    echo -e "${YELLOW}To add MCP server, merge this configuration:${NC}"
else
    echo -e "${GREEN}Creating new Claude Desktop config...${NC}"
fi

# Generate config JSON
cat > /tmp/claude_mcp_config.json << EOF
{
  "mcpServers": {
    "agentic-blogging-assistant": {
      "command": "python3",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "env": {
        "BACKEND_URL": "http://localhost:8000",
        "MCP_SERVER_NAME": "agentic-blogging-assistant",
        "LOG_LEVEL": "INFO",
        "PYTHONPATH": "$PROJECT_ROOT/root"
      }
    }
  }
}
EOF

echo -e "${GREEN}✅ Configuration generated at: ${BLUE}/tmp/claude_mcp_config.json${NC}"
echo ""

# Step 5: Instructions
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}[5/5] Setup Complete! Next Steps:${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "${YELLOW}📋 Configuration File Location:${NC}"
echo -e "   ${BLUE}$CLAUDE_CONFIG_FILE${NC}"
echo ""

if [ -f "$CLAUDE_CONFIG_FILE" ]; then
    echo -e "${YELLOW}⚙️  To Update Existing Config:${NC}"
    echo -e "   1. Open: ${BLUE}code $CLAUDE_CONFIG_FILE${NC}"
    echo -e "   2. Add the MCP server configuration from: ${BLUE}/tmp/claude_mcp_config.json${NC}"
    echo -e "   3. Or run: ${BLUE}cat /tmp/claude_mcp_config.json${NC}"
else
    echo -e "${YELLOW}⚙️  To Create New Config:${NC}"
    echo -e "   Run: ${BLUE}cp /tmp/claude_mcp_config.json $CLAUDE_CONFIG_FILE${NC}"
fi

echo ""
echo -e "${YELLOW}🔄 Restart Claude Desktop:${NC}"
echo -e "   1. Quit Claude Desktop completely (Cmd+Q on Mac)"
echo -e "   2. Reopen Claude Desktop"
echo -e "   3. MCP server will auto-start"
echo ""

echo -e "${YELLOW}✨ Test Commands in Claude Desktop:${NC}"
echo -e "   ${GREEN}• List all projects:${NC}"
echo -e "     'List all my blog projects'"
echo ""
echo -e "   ${GREEN}• Create new project:${NC}"
echo -e "     'Create a new blog project called Test Blog using Tech Blog Writer persona'"
echo ""
echo -e "   ${GREEN}• Complete automation:${NC}"
echo -e "     'Generate a complete blog about [topic] from my notebook'"
echo ""

echo -e "${YELLOW}📊 Monitoring:${NC}"
echo -e "   Backend logs: ${BLUE}tail -f /tmp/backend.log${NC}"
echo -e "   Backend health: ${BLUE}curl http://localhost:8000/health${NC}"
echo -e "   Claude logs: ${BLUE}~/Library/Logs/Claude/${NC}"
echo ""

echo -e "${YELLOW}🛑 Shutdown:${NC}"
if [ -f /tmp/backend.pid ]; then
    echo -e "   Stop backend: ${BLUE}kill \$(cat /tmp/backend.pid)${NC}"
fi
echo -e "   Or use: ${BLUE}./stop-testing.sh${NC}"
echo ""

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Ready for testing! Backend is running on port 8000${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
