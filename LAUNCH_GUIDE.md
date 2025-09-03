# 🚀 Launch Guide

Two ways to launch the Agentic Blogging Assistant:

## Option 1: Separate Terminals (Recommended)
```bash
./launch.sh
```

**What it does:**
- Opens **2 separate terminal windows**
- Backend (FastAPI) in one terminal: `http://localhost:8000`
- Frontend (Streamlit) in another terminal: `http://localhost:8501`
- Each service has its own dedicated terminal for logs and debugging

**Benefits:**
- Easy debugging - see logs separately
- Independent process control
- Clear visual separation
- Works on macOS (Terminal.app) and Linux (gnome-terminal/xterm)

## Option 2: Parallel Background Processes
```bash
./launch-parallel.sh
```

**What it does:**
- Runs both services as **background processes**
- Logs are saved to separate files
- Single terminal with process monitoring

**Benefits:**
- Works in any environment
- Centralized process management
- Log files for later inspection
- Good for CI/CD or headless environments

## Quick Start Commands

```bash
# Make scripts executable (first time only)
chmod +x launch.sh launch-parallel.sh

# Launch with separate terminals
./launch.sh

# Or launch with background processes
./launch-parallel.sh
```

## URLs After Launch

- **Frontend (Streamlit)**: http://localhost:8501
- **Backend (FastAPI)**: http://localhost:8000  
- **API Documentation**: http://localhost:8000/docs

## Stopping the Services

**Separate Terminals Mode:**
- Close each terminal window, or
- Press `Ctrl+C` in each terminal

**Parallel Mode:**
- Press `Ctrl+C` in the launch terminal
- Both services will be stopped automatically

## Troubleshooting

**Port already in use?**
```bash
# Check what's using the ports
lsof -i :8000  # Backend port
lsof -i :8501  # Frontend port

# Kill processes if needed
kill -9 <PID>
```

**Dependencies missing?**
```bash
# Install backend dependencies
cd root && pip install -r requirements.txt

# Install frontend dependencies
cd root/frontend && pip install -r requirements.txt
```