# Multi-stage build for PyAirtable Automation Services
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.6.1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8006

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8006/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]

# Development stage
FROM base as development

# Switch back to root to install dev dependencies
USER root

# Install development tools
RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    pytest-asyncio==0.21.1 \
    black==23.11.0 \
    isort==5.12.0 \
    flake8==6.1.0

# Switch back to app user
USER appuser

# Override command for development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", "--reload"]

# Production stage
FROM base as production

# Production optimizations
ENV WORKERS=4
ENV LOG_LEVEL=INFO

# Run with multiple workers in production
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006", "--workers", "4"]