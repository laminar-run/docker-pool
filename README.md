# Docker Script Execution Server

A production-ready Docker-based script execution server with custom container pool image support. This server provides a secure, isolated environment for executing untrusted scripts with configurable resource limits and custom runtime environments.

## Features

- **Container Pool Management**: Efficient container pooling for fast script execution
- **Custom Image Support**: Use custom Docker images with specific tools and libraries
- **Security**: Network isolation, resource limits, and security constraints
- **Production Ready**: Docker deployment with health checks and monitoring
- **Flexible Configuration**: Environment-based configuration with sensible defaults
- **Retry Logic**: Robust image pulling with exponential backoff
- **Metrics**: Built-in metrics and monitoring endpoints

## Quick Start

### 1. Basic Deployment

```bash
# Clone and navigate to the project
git clone <repository-url>
cd azurepoc

# Start with default Alpine Linux containers
docker-compose up -d

# Test the server
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "echo \"Hello World\"\ndate\npwd"}'
```

### 2. Using Custom Images

```bash
# Build a custom Python scientific image
cd custom-images/python-scientific
docker build -t python-scientific-executor .

# Use the custom image
BASE_IMAGE=python-scientific-executor docker-compose up -d
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key configuration options:

| Variable | Default | Description |
|----------|---------|-------------|
| `POOL_SIZE` | `5` | Number of containers in the pool |
| `BASE_IMAGE` | `alpine:latest` | Docker image for containers |
| `MEMORY_LIMIT` | `256m` | Memory limit per container |
| `CPU_LIMIT` | `0.5` | CPU limit per container |
| `TIMEOUT` | `30` | Script execution timeout (seconds) |
| `HOST_PORT` | `8080` | Host port to bind to |
| `CUSTOM_IMAGE_REGISTRY` | `` | Custom Docker registry URL |
| `CUSTOM_IMAGE_PULL_TIMEOUT` | `300` | Image pull timeout (seconds) |
| `CUSTOM_IMAGE_PULL_RETRIES` | `3` | Number of pull retry attempts |
| `CUSTOM_POOLS` | `` | Pre-warmed pools for custom images (format: "image1:size1,image2:size2") |

### Docker Compose

The `docker-compose.yml` file provides a complete production setup:

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## API Endpoints

### Execute Script

**POST** `/execute`

Execute a script in an isolated container. You can optionally specify a custom Docker image for the execution environment.

**Request Parameters:**
- `script` (required): The script to execute
- `stdin` (optional): Standard input for the script
- `image` (optional): Custom Docker image to use for execution

**Basic execution (uses default pool image):**
```bash
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{
    "script": "echo \"Hello World\"\ndate\npwd"
  }'
```

**Custom image execution:**
```bash
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{
    "script": "python3 -c \"import numpy; print(numpy.array([1,2,3]).sum())\"",
    "image": "python-scientific-executor"
  }'
```

**Response:**
```json
{
  "success": true,
  "stdout": "Hello World\nMon Jan 1 12:00:00 UTC 2024\n/tmp",
  "stderr": "",
  "exit_code": 0,
  "execution_time": 0.123,
  "error": null
}
```

**Custom Image Behavior:**
- If `image` is not specified, uses containers from the default pool
- If `image` is specified and a pool exists for that image, uses the pre-warmed pool (fast)
- If `image` is specified but no pool exists, creates a temporary container (slower)
- Custom images are automatically pulled if not available locally
- Registry prefix is added automatically if `CUSTOM_IMAGE_REGISTRY` is configured
- Image names are validated before use

## Multi-Pool Architecture

The server now supports multiple pre-warmed container pools for different images, providing optimal performance for frequently used custom environments.

### How It Works

**Default Pool**: Always created with the `BASE_IMAGE` (usually Alpine Linux)
**Custom Pools**: Additional pools for specific images, configured via `CUSTOM_POOLS`
**Temporary Containers**: Created on-demand for images without dedicated pools

### Performance Benefits

- **Pre-warmed Pools**: Instant execution for configured images (no container creation delay)
- **Resource Efficiency**: Containers are reused across requests
- **Automatic Scaling**: Pools maintain their configured size automatically
- **Graceful Fallback**: Unknown images still work via temporary containers

### Configuration

Configure custom pools using the `CUSTOM_POOLS` environment variable:

```bash
# Format: "image1:size1,image2:size2,image3:size3"
CUSTOM_POOLS=python-scientific-executor:3,nodejs-executor:2,multi-language-executor:1
```

**Example docker-compose.yml:**
```yaml
services:
  script-executor:
    environment:
      - BASE_IMAGE=alpine:latest
      - POOL_SIZE=5  # Default pool size
      - CUSTOM_POOLS=python-scientific-executor:3,nodejs-executor:2
```

### Pool Metrics

The `/metrics` endpoint now provides detailed information about all pools:

```json
{
  "pools_active": 3,
  "total_available_containers": 10,
  "pool_metrics": {
    "alpine:latest": {
      "pool_size": 5,
      "available_containers": 5,
      "total_executions": 10
    },
    "python-scientific-executor": {
      "pool_size": 3,
      "available_containers": 3,
      "total_executions": 5
    }
  }
}
```

### Testing Multi-Pools

```bash
# Test multi-pool functionality
./test_multi_pools.py

# Test with specific configuration
CUSTOM_POOLS=python-scientific-executor:2 ./test_multi_pools.py
```

### Health Check

**GET** `/health`

Check server health status.

```bash
curl http://localhost:8080/health
```

### Metrics

**GET** `/metrics`

Get server and pool metrics.

```bash
curl http://localhost:8080/metrics
```

## Custom Images

### Available Examples

1. **Python Scientific** (`custom-images/python-scientific/`)
   - Python 3.11 with NumPy, Pandas, SciPy, Matplotlib, Scikit-learn
   - Perfect for data science and machine learning scripts

2. **Node.js Runtime** (`custom-images/nodejs-runtime/`)
   - Node.js 18 with common packages (lodash, axios, moment)
   - Ideal for JavaScript/Node.js script execution

3. **Multi-Language** (`custom-images/multi-language/`)
   - Support for Python, Node.js, Java, Go, Ruby, Rust
   - Comprehensive environment for polyglot development

### Building Custom Images

```bash
# Build Python scientific image
cd custom-images/python-scientific
docker build -t python-scientific-executor .

# Build Node.js image
cd custom-images/nodejs-runtime
docker build -t nodejs-executor .

# Build multi-language image
cd custom-images/multi-language
docker build -t multi-language-executor .
```

### Using Custom Images

```bash
# Method 1: Environment variable
export BASE_IMAGE=python-scientific-executor
docker-compose up -d

# Method 2: Docker compose override
BASE_IMAGE=nodejs-executor docker-compose up -d

# Method 3: Update .env file
echo "BASE_IMAGE=multi-language-executor" >> .env
docker-compose up -d
```

## Security

### Container Security

- **Network Isolation**: Containers have no network access
- **Resource Limits**: CPU and memory constraints
- **Security Options**: `no-new-privileges`, capability dropping
- **Temporary Filesystem**: Isolated `/tmp` directory
- **Non-root User**: Containers run as non-privileged user

### Host Security

- **Docker Socket**: Mounted read-only where possible
- **User Permissions**: Server runs as non-root user
- **Resource Limits**: Container resource constraints
- **Health Checks**: Automatic health monitoring

## Monitoring

### Health Checks

The server includes built-in health checks:

```bash
# Docker health check
docker ps  # Shows health status

# Manual health check
curl http://localhost:8080/health
```

### Metrics

Monitor server performance:

```bash
curl http://localhost:8080/metrics
```

Metrics include:
- Total executions
- Success/failure rates
- Average execution time
- Pool statistics
- Container lifecycle metrics

### Logging

Configure logging level:

```bash
# Set log level
export LOG_LEVEL=DEBUG
docker-compose up -d

# View logs
docker-compose logs -f script-executor
```

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python server.py --host 0.0.0.0 --port 8080 --debug

# Run tests
python test_comprehensive.py
```

### Testing

```bash
# Test basic functionality
python test_server.py

# Comprehensive testing
python test_comprehensive.py

# Test with custom image
BASE_IMAGE=python-scientific-executor python test_server.py
```

## Production Deployment

### Docker Swarm

```yaml
# docker-stack.yml
version: '3.8'
services:
  script-executor:
    image: script-executor:latest
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - POOL_SIZE=10
      - BASE_IMAGE=python-scientific-executor
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

### Kubernetes

```yaml
# k8s-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: script-executor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: script-executor
  template:
    metadata:
      labels:
        app: script-executor
    spec:
      containers:
      - name: script-executor
        image: script-executor:latest
        ports:
        - containerPort: 8080
        env:
        - name: POOL_SIZE
          value: "10"
        - name: BASE_IMAGE
          value: "python-scientific-executor"
        volumeMounts:
        - name: docker-sock
          mountPath: /var/run/docker.sock
      volumes:
      - name: docker-sock
        hostPath:
          path: /var/run/docker.sock
```

## Docker Permission Fix

### Problem

When running the script-executor-server in a Docker container, you may encounter permission errors when the application tries to access the Docker daemon:

```
docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', PermissionError(13, 'Permission denied'))
```

This occurs because the container runs as a non-root user (`appuser`) but needs access to the Docker socket (`/var/run/docker.sock`) to manage containers.

### Solution

The application includes an automated Docker permission fix that:

1. **Detects the host's Docker group ID** automatically
2. **Creates a docker group** inside the container with the correct group ID
3. **Adds the appuser** to the docker group for socket access
4. **Maintains security** by keeping the non-root user approach

### Automatic Fix (Recommended)

The deployment script automatically handles Docker permissions:

```bash
# The deploy.sh script automatically detects and fixes Docker permissions
./deploy.sh

# For development environment
./deploy.sh --env development
```

### Manual Fix

If you need to fix permissions manually:

```bash
# Check current Docker permissions
./fix-docker-permissions.sh --check

# Apply automatic fix
./fix-docker-permissions.sh --fix

# Apply fix with specific Docker group ID
./fix-docker-permissions.sh --fix --gid 998
```

### Manual Configuration

If the automatic detection doesn't work, you can manually configure the Docker group ID:

1. **Find your Docker group ID:**
   ```bash
   # Method 1: Check docker socket group
   stat -c '%g' /var/run/docker.sock
   
   # Method 2: Check /etc/group
   getent group docker | cut -d: -f3
   ```

2. **Set the group ID in your .env file:**
   ```bash
   echo "DOCKER_GID=999" >> .env  # Replace 999 with your actual group ID
   ```

3. **Rebuild and restart:**
   ```bash
   docker-compose down
   docker-compose up -d --build
   ```

### Verification

After applying the fix, verify Docker access works:

```bash
# Check if the container can access Docker
docker-compose exec script-executor docker ps

# Test script execution
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "echo \"Docker permissions working!\""}'
```

### Technical Details

The fix works by:

1. **Dockerfile changes:**
   - Accepts `DOCKER_GID` build argument
   - Creates docker group with host's group ID
   - Adds `appuser` to docker group

2. **docker-compose.yml changes:**
   - Passes `DOCKER_GID` as build argument
   - Uses `group_add` to map docker group
   - Maintains Docker socket mounting

3. **Deployment script changes:**
   - Auto-detects Docker group ID
   - Updates .env file with correct group ID
   - Ensures compatibility across different hosts

### Compatibility

This solution works across different systems:
- **Linux distributions** (Ubuntu, CentOS, Debian, etc.)
- **Docker Desktop** on macOS and Windows
- **Cloud platforms** (AWS, GCP, Azure)
- **Container orchestration** (Docker Swarm, Kubernetes)

## Troubleshooting

### Common Issues

1. **Docker Connection Failed**
   ```bash
   # Check Docker daemon
   docker ps
   
   # Check socket permissions
   ls -la /var/run/docker.sock
   
   # Run permission fix
   ./fix-docker-permissions.sh --check
   ./fix-docker-permissions.sh --fix
   ```

2. **Image Pull Failures**
   ```bash
   # Check image name
   docker pull your-image-name
   
   # Check registry access
   docker login your-registry.com
   ```

3. **Container Creation Errors**
   ```bash
   # Check available resources
   docker system df
   
   # Clean up unused containers
   docker system prune
   ```

4. **Permission Denied Errors**
   ```bash
   # This is usually a Docker socket permission issue
   ./fix-docker-permissions.sh --check
   ./fix-docker-permissions.sh --fix
   
   # Rebuild containers after fix
   docker-compose down && docker-compose up -d --build
   ```

### Debug Mode

Enable debug logging:

```bash
LOG_LEVEL=DEBUG docker-compose up -d
docker-compose logs -f
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

[Your License Here]

## Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the custom images documentation