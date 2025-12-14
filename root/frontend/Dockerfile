# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the frontend application
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/cache /app/data/uploads

# Expose the port Streamlit runs on
EXPOSE 8501

# Health check (use PORT env var from Cloud Run)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8501}/_stcore/health || exit 1

# Run Streamlit (use PORT env var from Cloud Run, default to 8501)
CMD streamlit run new_app_api.py --server.port=${PORT:-8501} --server.address=0.0.0.0