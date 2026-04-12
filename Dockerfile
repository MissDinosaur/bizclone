# Multi-stage build for BizClone
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy ONLY requirements first for better caching
# COPY requirements-prod.txt requirements.txt ./
COPY requirements.txt ./

# Install Python dependencies from production-only file
# This layer will be cached and reused unless requirements change
RUN pip install --no-cache-dir -r requirements.txt psycopg2-binary

# Copy application code (changes here won't invalidate pip cache above)
COPY . .

# Create data directory for logs and file storage
RUN mkdir -p data logs

# Suppress verbose progress bars and model loading logs
ENV HF_HUB_DISABLE_PROGRESS_BARS=1
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run application
CMD ["python", "main.py"]