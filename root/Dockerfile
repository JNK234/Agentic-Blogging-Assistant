# ABOUTME: Dockerfile for Quibo FastAPI backend deployment to Cloud Run
# ABOUTME: Uses multi-stage build to optimize image size and reduce cold start times

# === Stage 1: Builder ===
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# === Stage 2: Runtime ===
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY backend/ ./backend/
COPY __init__.py .

# Create data directories (ephemeral in Cloud Run)
RUN mkdir -p /app/data/uploads /tmp/vector_store /app/data/cache

# Pre-download sentence transformer model during build to avoid cold start download
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080
ENV CHROMA_PERSIST_DIR=/tmp/vector_store

# Expose the port Cloud Run expects
EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=30s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start command with uvicorn
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
