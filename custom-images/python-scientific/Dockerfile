FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN useradd -m -s /bin/bash executor

# Set working directory
WORKDIR /tmp

# Copy requirements and install Python packages
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER executor

# Default command
CMD ["/bin/bash"]