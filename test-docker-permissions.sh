#!/bin/bash

# Test Docker Permissions Script
# This script tests if the Docker permission fix is working correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo "🔧 Testing Docker Permissions"
echo "============================="

# Check if containers are running
print_status "Checking if containers are running..."
if ! docker compose ps | grep -q "script-executor"; then
    print_error "Container is not running. Please start with: docker compose up -d --build"
    exit 1
fi

print_success "Container is running"

# Test Docker access from inside container
print_status "Testing Docker access from inside container..."
if docker compose exec -T script-executor docker ps > /dev/null 2>&1; then
    print_success "Docker access from container: WORKING"
else
    print_error "Docker access from container: FAILED"
    print_status "Checking container logs..."
    docker compose logs --tail=20 script-executor
    
    print_status "Debugging information:"
    echo "Host Docker socket permissions:"
    ls -la /var/run/docker.sock
    
    echo "Container user info:"
    docker compose exec -T script-executor id
    
    echo "Container groups:"
    docker compose exec -T script-executor groups
    
    echo "Docker group in container:"
    docker compose exec -T script-executor getent group docker || echo "Docker group not found"
    
    print_error "Docker permission fix failed. Try rebuilding with: docker compose down && docker compose up -d --build"
    exit 1
fi

# Test API endpoint
print_status "Testing API endpoint..."
if curl -f -s http://localhost:8080/health > /dev/null; then
    print_success "API health endpoint: WORKING"
else
    print_error "API health endpoint: FAILED"
    print_status "Container may still be starting up. Check logs with: docker compose logs -f"
    exit 1
fi

# Test script execution
print_status "Testing script execution..."
response=$(curl -f -s -X POST http://localhost:8080/execute \
    -H "Content-Type: application/json" \
    -d '{"script": "echo \"Docker permissions test successful\""}' 2>/dev/null || echo "")

if echo "$response" | grep -q "success.*true"; then
    print_success "Script execution: WORKING"
    echo "Response: $response"
else
    print_error "Script execution: FAILED"
    echo "Response: $response"
    print_status "Check container logs for more details: docker compose logs script-executor"
    exit 1
fi

print_success "All Docker permission tests passed! 🎉"
echo ""
echo "Summary:"
echo "✅ Container is running"
echo "✅ Docker socket access from container works"
echo "✅ API health endpoint responds"
echo "✅ Script execution works"
echo ""
echo "Your Docker permission fix is working correctly!"