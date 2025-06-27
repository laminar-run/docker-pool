FROM ubuntu:22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and multiple language runtimes
RUN apt-get update && apt-get install -y \
    # Basic tools
    curl \
    wget \
    git \
    unzip \
    build-essential \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    # Node.js
    nodejs \
    npm \
    # Java
    openjdk-11-jdk \
    # Go
    golang-go \
    # Ruby
    ruby \
    ruby-dev \
    # Rust (via rustup)
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Create non-root user
RUN useradd -m -s /bin/bash executor

# Copy and run installation script
COPY install-tools.sh /tmp/
RUN chmod +x /tmp/install-tools.sh && \
    /tmp/install-tools.sh && \
    rm /tmp/install-tools.sh

# Set up user environment
RUN chown -R executor:executor /home/executor

# Prepare workspace directory for file attachments
RUN mkdir -p /workspace && \
    chown -R executor:executor /workspace

# Switch to non-root user
USER executor

# Set working directory
WORKDIR /tmp

# Set environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV GOPATH=/home/executor/go
ENV PATH="${PATH}:/home/executor/.local/bin:/home/executor/go/bin"

# Default command
CMD ["/bin/bash"]