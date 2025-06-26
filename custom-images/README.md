# Custom Container Images

This directory contains examples and documentation for creating custom container images for the script execution server.

## Overview

The script execution server supports custom container images to provide specific runtime environments with pre-installed tools, libraries, or binaries that your scripts may require.

## Quick Start

1. **Build a custom image:**
   ```bash
   cd custom-images/python-scientific
   docker build -t my-custom-executor .
   ```

2. **Use the custom image:**
   ```bash
   # Set environment variable
   export BASE_IMAGE=my-custom-executor
   
   # Or use docker-compose
   BASE_IMAGE=my-custom-executor docker-compose up
   ```

## Directory Structure

```
custom-images/
├── README.md                 # This file
├── python-scientific/        # Python with scientific libraries
│   ├── Dockerfile
│   └── requirements.txt
├── nodejs-runtime/           # Node.js runtime environment
│   ├── Dockerfile
│   └── package.json
└── multi-language/           # Multiple language support
    ├── Dockerfile
    └── install-tools.sh
```

## Creating Custom Images

### Basic Requirements

Your custom image must:

1. **Base Image**: Start from a lightweight Linux distribution (Alpine, Ubuntu, etc.)
2. **Shell Access**: Provide `/bin/sh` or `/bin/bash` for script execution
3. **Security**: Follow security best practices (non-root user, minimal privileges)
4. **Size**: Keep image size reasonable for faster container startup

### Example Dockerfile Template

```dockerfile
FROM alpine:latest

# Install required packages
RUN apk add --no-cache \
    bash \
    curl \
    your-required-packages

# Create non-root user
RUN addgroup -g 1000 executor && \
    adduser -u 1000 -G executor -s /bin/sh -D executor

# Install your specific tools/libraries
COPY install-script.sh /tmp/
RUN chmod +x /tmp/install-script.sh && \
    /tmp/install-script.sh && \
    rm /tmp/install-script.sh

# Switch to non-root user
USER executor

# Set working directory
WORKDIR /tmp

# Default command (will be overridden by the server)
CMD ["/bin/sh"]
```

## Configuration Options

### Environment Variables

- `BASE_IMAGE`: The Docker image to use for containers (default: `alpine:latest`)
- `CUSTOM_IMAGE_REGISTRY`: Custom registry URL (e.g., `my-registry.com`)
- `CUSTOM_IMAGE_PULL_TIMEOUT`: Timeout for pulling images in seconds (default: 300)
- `CUSTOM_IMAGE_PULL_RETRIES`: Number of retry attempts for pulling images (default: 3)

### Docker Compose Configuration

```yaml
services:
  script-executor:
    environment:
      - BASE_IMAGE=my-custom-executor:latest
      - CUSTOM_IMAGE_REGISTRY=my-registry.com
      - CUSTOM_IMAGE_PULL_TIMEOUT=600
      - CUSTOM_IMAGE_PULL_RETRIES=5
```

## Security Considerations

### Image Security

1. **Use official base images** from trusted sources
2. **Keep images updated** with latest security patches
3. **Minimize attack surface** by installing only necessary packages
4. **Use non-root users** inside containers
5. **Scan images** for vulnerabilities before deployment

### Runtime Security

The server automatically applies these security measures:
- Network isolation (`network_disabled=True`)
- Resource limits (CPU, memory)
- Security options (`no-new-privileges`, capability dropping)
- Temporary filesystem for `/tmp`
- Read-only root filesystem where possible

## Testing Custom Images

1. **Build your image:**
   ```bash
   docker build -t test-executor ./custom-images/your-image/
   ```

2. **Test locally:**
   ```bash
   docker run --rm -it test-executor /bin/sh -c "your-test-command"
   ```

3. **Test with the server:**
   ```bash
   BASE_IMAGE=test-executor python server.py
   ```

4. **Run test scripts:**
   ```bash
   python test_server.py
   ```

## Troubleshooting

### Common Issues

1. **Image not found**: Ensure the image name is correct and accessible
2. **Permission denied**: Check that the image has proper user permissions
3. **Command not found**: Verify required tools are installed in the image
4. **Timeout errors**: Increase `CUSTOM_IMAGE_PULL_TIMEOUT` for large images

### Debugging

1. **Check server logs** for detailed error messages
2. **Test image manually** with `docker run`
3. **Verify image contents** with `docker run --rm -it image-name /bin/sh`
4. **Check network connectivity** for registry access

## Best Practices

1. **Layer optimization**: Order Dockerfile commands to maximize cache efficiency
2. **Multi-stage builds**: Use multi-stage builds to reduce final image size
3. **Health checks**: Include health check commands in your images
4. **Documentation**: Document your custom images and their capabilities
5. **Versioning**: Use specific version tags rather than `latest`
6. **Testing**: Thoroughly test images before production deployment

## Examples

See the example directories for specific use cases:
- `python-scientific/`: Python with NumPy, Pandas, SciPy
- `nodejs-runtime/`: Node.js with common packages
- `multi-language/`: Support for multiple programming languages