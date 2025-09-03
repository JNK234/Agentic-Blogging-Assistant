#!/bin/bash

# ABOUTME: Alternative launch script that runs both services in parallel in the same terminal
# ABOUTME: Uses background processes with clear output separation and process management

echo "🚀 Starting Agentic Blogging Assistant (Parallel Mode)..."
echo "========================================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/root"

# Function to kill background processes on script exit
cleanup() {
    echo ""
    echo "🛑 Shutting down applications..."
    if [[ -n "$BACKEND_PID" ]]; then
        kill $BACKEND_PID 2>/dev/null
        echo "   ✅ Backend stopped"
    fi
    if [[ -n "$FRONTEND_PID" ]]; then
        kill $FRONTEND_PID 2>/dev/null
        echo "   ✅ Frontend stopped"
    fi
    echo "🏁 All applications stopped successfully"
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

# Create log files for each service
BACKEND_LOG="/tmp/agentic-backend.log"
FRONTEND_LOG="/tmp/agentic-frontend.log"

# Start Backend (FastAPI) in background
echo "🔧 Starting FastAPI Backend..."
cd "$ROOT_DIR/backend"
(
    echo "🔧 FastAPI Backend Starting..." 
    echo "📍 Directory: $ROOT_DIR/backend"
    echo "🌐 URL: http://localhost:8000"
    echo "📚 Docs: http://localhost:8000/docs"
    echo "=================="
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
) > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Wait a moment for backend to start
echo "   ⏳ Waiting for backend to initialize..."
sleep 4

# Start Frontend (Streamlit) in background
echo "🎨 Starting Streamlit Frontend..."
cd "$ROOT_DIR/frontend"
(
    echo "🎨 Streamlit Frontend Starting..."
    echo "📍 Directory: $ROOT_DIR/frontend"
    echo "🌐 URL: http://localhost:8501"
    echo "=================="
    python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0
) > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "✅ Applications started successfully!"
echo "========================================================"
echo "🔧 Backend (FastAPI):   http://localhost:8000"
echo "🎨 Frontend (Streamlit): http://localhost:8501"
echo "📚 API Documentation:   http://localhost:8000/docs"
echo "========================================================"
echo "📋 Log files:"
echo "   Backend:  $BACKEND_LOG"
echo "   Frontend: $FRONTEND_LOG"
echo ""
echo "💡 Use 'tail -f $BACKEND_LOG' to monitor backend logs"
echo "💡 Use 'tail -f $FRONTEND_LOG' to monitor frontend logs"
echo "💡 Press Ctrl+C to stop both applications"
echo ""

# Monitor both processes and show their status
while true; do
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo "⚠️  Backend process stopped unexpectedly!"
        break
    fi
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo "⚠️  Frontend process stopped unexpectedly!"
        break
    fi
    sleep 5
done

# If we get here, one process died, so clean up the other
cleanup