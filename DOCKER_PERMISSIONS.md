# Docker Permission Fix Guide

This document provides comprehensive guidance for resolving Docker socket permission issues when running the script-executor-server in containers.

## Problem Description

When the script-executor-server runs inside a Docker container, it needs to access the host's Docker daemon to create and manage execution containers. This requires access to the Docker socket (`/var/run/docker.sock`), which is typically owned by the `docker` group.

### Common Error Messages

```
docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', PermissionError(13, 'Permission denied'))
```

```
requests.exceptions.ConnectionError: ('Connection aborted.', PermissionError(13, 'Permission denied'))
```

```
docker.errors.APIError: 500 Server Error: Internal Server Error ("dial unix /var/run/docker.sock: connect: permission denied")
```

## Root Cause

The issue occurs because:

1. The container runs as a non-root user (`appuser`) for security
2. The Docker socket is mounted from the host system
3. The host's Docker socket is owned by the `docker` group
4. The container's `appuser` is not in the docker group
5. The docker group ID inside the container doesn't match the host's docker group ID

## Solution Overview

Our solution maintains security while fixing permissions by:

1. **Auto-detecting** the host's Docker group ID
2. **Creating** a docker group inside the container with the correct group ID
3. **Adding** the appuser to the docker group
4. **Preserving** the non-root user security model

## Implementation Details

### 1. Dockerfile Changes

```dockerfile
# Build argument for Docker group ID (passed from docker-compose)
ARG DOCKER_GID=999

# Create docker group with the host's docker group ID
RUN groupadd -g ${DOCKER_GID} docker || true

# Create non-root user for security and add to docker group
RUN useradd -m -s /bin/bash appuser && \
    usermod -aG docker appuser
```

### 2. Docker Compose Changes

```yaml
services:
  script-executor:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        DOCKER_GID: ${DOCKER_GID:-999}
    environment:
      - DOCKER_GID=${DOCKER_GID:-999}
    group_add:
      - ${DOCKER_GID:-999}
```

### 3. Deployment Script Integration

The deployment script automatically:
- Detects the host's Docker group ID
- Updates the `.env` file with the correct group ID
- Rebuilds containers with proper permissions

## Usage Instructions

### Automatic Fix (Recommended)

```bash
# Deploy with automatic permission fix
./deploy.sh

# For development
./deploy.sh --env development
```

### Manual Permission Fix

```bash
# Check current permissions
./fix-docker-permissions.sh --check

# Apply automatic fix
./fix-docker-permissions.sh --fix

# Apply fix with specific group ID
./fix-docker-permissions.sh --fix --gid 998
```

### Manual Configuration

If automatic detection fails:

```bash
# 1. Find Docker group ID
stat -c '%g' /var/run/docker.sock

# 2. Set in environment
echo "DOCKER_GID=999" >> .env  # Replace with actual ID

# 3. Rebuild
docker-compose down && docker-compose up -d --build
```

## Verification Steps

### 1. Check Docker Socket Permissions

```bash
# Check socket ownership and permissions
ls -la /var/run/docker.sock

# Expected output similar to:
# srw-rw---- 1 root docker 0 Jan 1 12:00 /var/run/docker.sock
```

### 2. Verify Container Access

```bash
# Test Docker access from inside container
docker-compose exec script-executor docker ps

# Should list containers without permission errors
```

### 3. Test Script Execution

```bash
# Test the API endpoint
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "echo \"Docker permissions working!\""}'

# Expected response:
# {"success": true, "stdout": "Docker permissions working!\n", ...}
```

## Troubleshooting

### Issue: Auto-detection Fails

**Symptoms:**
- Script can't detect Docker group ID
- Falls back to default GID 999

**Solutions:**
```bash
# Method 1: Check socket group
stat -c '%g' /var/run/docker.sock

# Method 2: Check /etc/group
getent group docker | cut -d: -f3

# Method 3: Manual override
./fix-docker-permissions.sh --fix --gid YOUR_GID
```

### Issue: Group Already Exists Error

**Symptoms:**
```
groupadd: group 'docker' already exists
```

**Solution:**
This is expected and handled by the `|| true` in the Dockerfile. The error is non-fatal.

### Issue: Still Getting Permission Denied

**Possible Causes:**
1. Container wasn't rebuilt after applying fix
2. Wrong Docker group ID detected
3. SELinux or AppArmor restrictions

**Solutions:**
```bash
# 1. Force rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 2. Verify group ID
./fix-docker-permissions.sh --check

# 3. Check for security restrictions
# SELinux: sestatus
# AppArmor: aa-status
```

### Issue: Works on Some Systems, Not Others

**Cause:** Different systems have different Docker group IDs

**Solution:** The auto-detection handles this, but you can verify:

```bash
# On each system, check the group ID
stat -c '%g' /var/run/docker.sock

# Should be automatically detected and configured
```

## Security Considerations

### What We Maintain

- ✅ **Non-root execution**: Container still runs as `appuser`
- ✅ **Minimal privileges**: Only Docker socket access added
- ✅ **No new capabilities**: No additional Linux capabilities
- ✅ **Resource limits**: All existing limits preserved

### What We Add

- ➕ **Docker group membership**: Allows socket access
- ➕ **Group mapping**: Maps host docker group to container

### Security Best Practices

1. **Monitor Docker usage**: Log all container operations
2. **Limit base images**: Restrict which images can be used
3. **Network isolation**: Keep execution containers isolated
4. **Resource limits**: Maintain CPU/memory constraints
5. **Regular updates**: Keep Docker and base images updated

## Platform-Specific Notes

### Linux (Ubuntu/Debian/CentOS)

- Docker group typically has GID 999 or 998
- Auto-detection works reliably
- No additional configuration needed

### Docker Desktop (macOS/Windows)

- Docker socket is virtualized
- Group ID may vary
- Auto-detection handles differences

### Cloud Platforms

#### AWS ECS/EC2
- Standard Docker installation
- Group ID typically 999
- Works with standard configuration

#### Google Cloud Run/GKE
- May require additional IAM permissions
- Docker socket access varies by setup

#### Azure Container Instances
- Limited Docker-in-Docker support
- May need alternative deployment approach

## Advanced Configuration

### Custom Docker Socket Path

If Docker socket is in a non-standard location:

```yaml
# docker-compose.yml
volumes:
  - /custom/path/docker.sock:/var/run/docker.sock
```

### Multiple Docker Daemons

For systems with multiple Docker daemons:

```bash
# Specify which daemon to use
export DOCKER_HOST=unix:///var/run/docker-alt.sock
./deploy.sh
```

### Rootless Docker

For rootless Docker installations:

```bash
# Rootless Docker uses different socket path
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
./fix-docker-permissions.sh --check
```

## Testing the Fix

### Automated Testing

```bash
# Run comprehensive tests
python test_comprehensive.py

# Test Docker permissions specifically
./fix-docker-permissions.sh --check
```

### Manual Testing

```bash
# 1. Test container creation
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "echo test"}'

# 2. Test custom image usage
curl -X POST http://localhost:8080/execute \
  -H "Content-Type: application/json" \
  -d '{"script": "python3 --version", "image": "python:3.11-alpine"}'

# 3. Check metrics
curl http://localhost:8080/metrics
```

## Support

If you continue to experience Docker permission issues:

1. **Run diagnostics**: `./fix-docker-permissions.sh --check`
2. **Check logs**: `docker-compose logs script-executor`
3. **Verify setup**: Ensure Docker daemon is running and accessible
4. **Platform-specific**: Check platform-specific notes above
5. **Create issue**: Include diagnostic output and system information

## References

- [Docker Socket Security](https://docs.docker.com/engine/security/)
- [Docker Group Management](https://docs.docker.com/engine/install/linux-postinstall/)
- [Container Security Best Practices](https://docs.docker.com/develop/security-best-practices/)