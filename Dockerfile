# Use Python 3.11 slim image for smaller size and better security
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Build argument for Docker group ID (passed from docker-compose)
ARG DOCKER_GID=999

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create docker group with the host's docker group ID
RUN groupadd -g ${DOCKER_GID} docker || true

# Create non-root user for security and add to docker group
RUN useradd -m -s /bin/bash appuser && \
    usermod -aG docker appuser

# Create app directory
WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .
COPY custom-images/ ./custom-images/

# Create necessary directories and set permissions
RUN mkdir -p /app/logs /app/tmp && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Default command
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8080"]