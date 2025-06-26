FROM node:18-alpine

# Install additional tools
RUN apk add --no-cache \
    bash \
    curl \
    git \
    python3 \
    make \
    g++

# Create non-root user
RUN adduser -s /bin/bash -D executor

# Set working directory
WORKDIR /tmp

# Copy package.json and install dependencies
COPY package.json /tmp/
RUN npm install --global --production

# Create a local node_modules for user scripts
RUN mkdir -p /home/executor/node_modules && \
    chown -R executor:executor /home/executor

# Switch to non-root user
USER executor

# Set NODE_PATH for global modules
ENV NODE_PATH=/usr/local/lib/node_modules

# Default command
CMD ["/bin/bash"]