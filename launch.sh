#!/bin/bash

# ABOUTME: Launch script for Agentic Blogging Assistant - starts backend and frontend in separate terminals
# ABOUTME: Handles macOS Terminal app and cross-platform terminal detection for parallel service execution

echo "🚀 Starting Agentic Blogging Assistant..."
echo "================================================"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR/root"

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

# Detect operating system and launch accordingly
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - Use Terminal.app
    echo "🔧 Launching FastAPI Backend in new terminal..."
    osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR/backend' && echo '🔧 FastAPI Backend Starting...' && echo '📍 Directory: $ROOT_DIR/backend' && echo '🌐 URL: http://localhost:8000' && echo '📚 Docs: http://localhost:8000/docs' && echo '' && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload\""
    
    # Wait a moment for backend to start
    sleep 2
    
    echo "🎨 Launching Streamlit Frontend in new terminal..."
    osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR/frontend' && echo '🎨 Streamlit Frontend Starting...' && echo '📍 Directory: $ROOT_DIR/frontend' && echo '🌐 URL: http://localhost:8501' && echo '' && python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0\""

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - Try common terminal emulators
    if command -v gnome-terminal &> /dev/null; then
        echo "🔧 Launching FastAPI Backend in new terminal..."
        gnome-terminal --title="FastAPI Backend" -- bash -c "cd '$ROOT_DIR/backend' && echo '🔧 FastAPI Backend Starting...' && echo '📍 Directory: $ROOT_DIR/backend' && echo '🌐 URL: http://localhost:8000' && echo '📚 Docs: http://localhost:8000/docs' && echo '' && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload; exec bash"
        
        sleep 2
        
        echo "🎨 Launching Streamlit Frontend in new terminal..."
        gnome-terminal --title="Streamlit Frontend" -- bash -c "cd '$ROOT_DIR/frontend' && echo '🎨 Streamlit Frontend Starting...' && echo '📍 Directory: $ROOT_DIR/frontend' && echo '🌐 URL: http://localhost:8501' && echo '' && python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0; exec bash"
        
    elif command -v xterm &> /dev/null; then
        echo "🔧 Launching FastAPI Backend in new terminal..."
        xterm -T "FastAPI Backend" -e "cd '$ROOT_DIR/backend' && echo '🔧 FastAPI Backend Starting...' && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload; bash" &
        
        sleep 2
        
        echo "🎨 Launching Streamlit Frontend in new terminal..."
        xterm -T "Streamlit Frontend" -e "cd '$ROOT_DIR/frontend' && echo '🎨 Streamlit Frontend Starting...' && python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0; bash" &
        
    else
        echo "⚠️  No suitable terminal emulator found. Falling back to background processes..."
        # Fallback to background processes
        cd "$ROOT_DIR/backend"
        python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
        BACKEND_PID=$!
        
        sleep 3
        
        cd "$ROOT_DIR/frontend"
        python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0 &
        FRONTEND_PID=$!
        
        trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
    fi

else
    echo "⚠️  Unsupported operating system. Falling back to background processes..."
    # Fallback to background processes
    cd "$ROOT_DIR/backend"
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    
    sleep 3
    
    cd "$ROOT_DIR/frontend"
    python -m streamlit run new_app_api.py --server.port 8501 --server.address 0.0.0.0 &
    FRONTEND_PID=$!
    
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
fi

echo ""
echo "✅ Applications launching in separate terminals!"
echo "================================================"
echo "🔧 Backend (FastAPI):   http://localhost:8000"
echo "🎨 Frontend (Streamlit): http://localhost:8501"
echo "📚 API Documentation:   http://localhost:8000/docs"
echo "================================================"
echo "💡 Each service runs in its own terminal window"
echo "💡 Close the terminal windows to stop the services"
echo "💡 Or use Ctrl+C in each terminal"
echo ""

# If we're using background processes, wait for them
if [[ -n "$BACKEND_PID" && -n "$FRONTEND_PID" ]]; then
    echo "Press Ctrl+C to stop both applications"
    wait $BACKEND_PID $FRONTEND_PID
fi 