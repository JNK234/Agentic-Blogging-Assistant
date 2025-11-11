#!/bin/bash
# ABOUTME: Shutdown script for the Agentic Blogging Assistant testing environment
# ABOUTME: Stops the backend server and cleans up temporary files

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Stopping Agentic Blogging Assistant Servers${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Stop backend if PID file exists
if [ -f /tmp/backend.pid ]; then
    BACKEND_PID=$(cat /tmp/backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${YELLOW}Stopping backend server (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID
        sleep 2

        # Force kill if still running
        if ps -p $BACKEND_PID > /dev/null 2>&1; then
            echo -e "${RED}Force killing backend...${NC}"
            kill -9 $BACKEND_PID
        fi

        echo -e "${GREEN}✅ Backend stopped${NC}"
    else
        echo -e "${YELLOW}⚠️  Backend process not found${NC}"
    fi
    rm -f /tmp/backend.pid
else
    echo -e "${YELLOW}⚠️  No backend PID file found${NC}"

    # Try to find and kill any running uvicorn processes
    UVICORN_PIDS=$(pgrep -f "uvicorn main:app")
    if [ -n "$UVICORN_PIDS" ]; then
        echo -e "${YELLOW}Found running uvicorn processes: $UVICORN_PIDS${NC}"
        echo -e "${YELLOW}Stopping them...${NC}"
        echo "$UVICORN_PIDS" | xargs kill
        echo -e "${GREEN}✅ Uvicorn processes stopped${NC}"
    fi
fi

# Clean up log files (optional)
if [ -f /tmp/backend.log ]; then
    echo -e "${YELLOW}Backend logs saved at: ${BLUE}/tmp/backend.log${NC}"
    echo -e "${YELLOW}Remove logs? (y/N): ${NC}"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -f /tmp/backend.log
        echo -e "${GREEN}✅ Logs removed${NC}"
    fi
fi

echo ""
echo -e "${GREEN}✅ Shutdown complete${NC}"
echo -e "${YELLOW}Note: Claude Desktop MCP server will stop automatically when you quit Claude${NC}"
echo ""
