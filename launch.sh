#!/bin/bash

# Agentic Blogging Assistant Launcher
# This script launches both the FastAPI backend and Streamlit frontend

echo "🚀 Starting Agentic Blogging Assistant..."
echo "================================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/root"

# Function to kill background processes on script exit
cleanup() {
    echo ""
    echo "🛑 Shutting down applications..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "✅ Applications stopped successfully"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if required directories exist
if [ ! -d "$ROOT_DIR/backend" ] || [ ! -d "$ROOT_DIR/frontend" ]; then
    echo "❌ Error: Required directories not found!"
    echo "Make sure you're running this script from the Agentic-Blogging-Assistant directory"
    exit 1
fi

# Check if main files exist
if [ ! -f "$ROOT_DIR/backend/main.py" ]; then
    echo "❌ Error: Backend main.py not found!"
    exit 1
fi

if [ ! -f "$ROOT_DIR/frontend/new_app_api.py" ]; then
    echo "❌ Error: Frontend new_app_api.py not found!"
    exit 1
fi

# Start Backend (FastAPI)
echo "🔧 Starting FastAPI Backend..."
cd "$ROOT_DIR/backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start Frontend (Streamlit)
echo "🎨 Starting Streamlit Frontend..."
cd "$ROOT_DIR/frontend"
python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0 &
FRONTEND_PID=$!

echo ""
echo "✅ Applications started successfully!"
echo "================================================"
echo "🔧 Backend (FastAPI):  http://localhost:8000"
echo "🎨 Frontend (Streamlit): http://localhost:8501"
echo "📚 API Documentation:   http://localhost:8000/docs"
echo "================================================"
echo "Press Ctrl+C to stop both applications"
echo ""

# Wait for both processes to complete
wait $BACKEND_PID $FRONTEND_PID 