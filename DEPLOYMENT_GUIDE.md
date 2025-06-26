# Quick Deployment Guide

This guide provides step-by-step instructions for deploying the script-executor-server with Docker permission fixes.

## Prerequisites

- Docker installed and running
- Docker Compose (V1 or V2) available
- User has access to Docker daemon

## Quick Start (Recommended)

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd laminar-dev
```

### 2. Deploy with Automatic Permission Fix

```bash
# Deploy with automatic Docker permission detection and fix
./deploy.sh

# For development environment
./deploy.sh --env development
```

The deployment script will automatically:
- ✅ Detect Docker Compose command (V1 or V2)
- ✅ Detect your system's Docker group ID
- ✅ Configure proper permissions
- ✅ Build and start containers
- ✅ Run health checks
- ✅ Provide deployment summary

### 3. Verify Deployment

```bash
# Test the service
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "echo \"Hello World!\""}'

# Check health
curl http://localhost:8080/health

# View metrics
curl http://localhost:8080/metrics
```

## Manual Deployment (If Needed)

### 1. Check Docker Permissions

```bash
# Check current Docker setup
./fix-docker-permissions.sh --check
```

### 2. Apply Permission Fix (If Needed)

```bash
# Apply automatic fix
./fix-docker-permissions.sh --fix

# Or with specific group ID
./fix-docker-permissions.sh --fix --gid 999
```

### 3. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration if needed
nano .env
```

### 4. Deploy

```bash
# For Docker Compose V2 (modern Docker installations)
docker compose up -d --build

# For Docker Compose V1 (legacy installations)
docker-compose up -d --build

# Check status
docker compose ps  # or docker-compose ps

# View logs
docker compose logs -f  # or docker-compose logs -f
```

## Configuration Options

### Environment Variables (.env file)

```bash
# Container Pool Configuration
POOL_SIZE=5                    # Number of containers in pool
BASE_IMAGE=alpine:latest       # Default container image
MEMORY_LIMIT=256m             # Memory limit per container
CPU_LIMIT=0.5                 # CPU limit per container
TIMEOUT=30                    # Script execution timeout

# Server Configuration
HOST_PORT=8080                # Port to bind to
FLASK_ENV=production          # Environment mode
LOG_LEVEL=INFO               # Logging level

# Docker Configuration (auto-configured by deploy script)
DOCKER_GID=999               # Docker group ID for permissions
```

### Custom Images

```bash
# Use Python scientific image
BASE_IMAGE=python-scientific-executor ./deploy.sh

# Use Node.js image
BASE_IMAGE=nodejs-executor ./deploy.sh

# Use multi-language image
BASE_IMAGE=multi-language-executor ./deploy.sh
```

## Docker Compose Commands

The deployment script automatically detects whether you have Docker Compose V1 (`docker-compose`) or V2 (`docker compose`). Here are the equivalent commands for both:

### Docker Compose V2 (Recommended)
```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f

# Rebuild and restart
docker compose up -d --build

# Check status
docker compose ps
```

### Docker Compose V1 (Legacy)
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Rebuild and restart
docker-compose up -d --build

# Check status
docker-compose ps
```

## Troubleshooting

### Permission Denied Errors

```bash
# Check and fix Docker permissions
./fix-docker-permissions.sh --check
./fix-docker-permissions.sh --fix

# Rebuild containers (script will use correct compose command)
./deploy.sh
```

### Docker Compose Not Found

If you get "Docker Compose is not installed":

```bash
# Check what's available
docker --version
docker compose version  # For V2
docker-compose --version  # For V1

# Install Docker Compose V1 if needed (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker-compose

# Or install Docker Compose V2 (recommended)
# Usually included with modern Docker installations
```

### Service Not Starting

```bash
# Check logs (script detects correct command)
./deploy.sh  # Will show logs if deployment fails

# Manual log check
docker compose logs script-executor  # or docker-compose logs script-executor

# Check Docker daemon
docker ps

# Verify port availability
netstat -tlnp | grep 8080
```

### Container Creation Failures

```bash
# Check Docker resources
docker system df

# Clean up if needed
docker system prune

# Check image availability
docker images
```

## Management Commands

The deployment script provides the correct commands for your system in the deployment summary. Common patterns:

### Start/Stop Service

```bash
# Using deployment script (recommended)
./deploy.sh                    # Start with auto-detection
./deploy.sh --env development  # Development mode

# Manual commands (use appropriate version)
docker compose up -d           # V2
docker-compose up -d           # V1

docker compose down            # V2
docker-compose down            # V1
```

### Logs and Monitoring

```bash
# View logs
docker compose logs -f script-executor    # V2
docker-compose logs -f script-executor    # V1

# Check health
curl http://localhost:8080/health

# Monitor metrics
curl http://localhost:8080/metrics

# Watch logs in real-time
docker compose logs -f --tail=100         # V2
docker-compose logs -f --tail=100         # V1
```

### Updates and Maintenance

```bash
# Update and rebuild (recommended)
git pull
./deploy.sh

# Manual update
docker compose down && docker compose up -d --build    # V2
docker-compose down && docker-compose up -d --build    # V1

# Clean up old images
docker image prune
```

## Testing

### Basic Functionality

```bash
# Test script execution
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "echo \"Test successful\"\ndate\npwd"}'
```

### Custom Image Testing

```bash
# Test with Python
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "python3 -c \"print(\\\"Python works!\\\")\"", "image": "python:3.11-alpine"}'
```

### Comprehensive Testing

```bash
# Run test suite
python test_comprehensive.py

# Test multi-pool functionality
python test_multi_pools.py
```

## Production Considerations

### Security

- ✅ Containers run as non-root user
- ✅ Network isolation enabled
- ✅ Resource limits enforced
- ✅ Docker socket permissions properly configured

### Monitoring

- Set up log aggregation
- Monitor `/health` and `/metrics` endpoints
- Configure alerts for service failures
- Monitor Docker resource usage

### Scaling

```bash
# Scale with Docker Compose
docker compose up -d --scale script-executor=3    # V2
docker-compose up -d --scale script-executor=3    # V1

# Or use Docker Swarm/Kubernetes for production scaling
```

## Support

### Getting Help

1. **Check logs**: Use the deployment script or manual commands
2. **Run diagnostics**: `./fix-docker-permissions.sh --check`
3. **Review documentation**: See `README.md` and `DOCKER_PERMISSIONS.md`
4. **Test configuration**: Run `test_comprehensive.py`

### Common Solutions

| Issue | Solution |
|-------|----------|
| Permission denied | `./fix-docker-permissions.sh --fix` |
| Docker Compose not found | Install docker-compose or use modern Docker |
| Port already in use | Change `HOST_PORT` in `.env` |
| Out of disk space | `docker system prune` |
| Image pull failures | Check internet connection and image names |
| Container won't start | Check logs with deployment script |

## Next Steps

After successful deployment:

1. **Integrate with your application**: Use the `/execute` API endpoint
2. **Configure custom images**: Build images for your specific use cases
3. **Set up monitoring**: Monitor health and metrics endpoints
4. **Scale as needed**: Adjust `POOL_SIZE` and container resources
5. **Secure for production**: Review security settings and access controls

For detailed information, see:
- `README.md` - Complete documentation
- `DOCKER_PERMISSIONS.md` - Docker permission troubleshooting
- `custom-images/` - Custom image examples