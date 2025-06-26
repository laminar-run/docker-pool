#!/bin/bash

# Docker Permission Fix Script for Script Executor Server
# This script fixes Docker socket permission issues when running in containers

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Docker Permission Fix Script"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --check         Check current Docker permissions"
    echo "  --fix           Apply Docker permission fixes"
    echo "  --gid GID       Use specific Docker group ID"
    echo "  --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --check                    # Check current permissions"
    echo "  $0 --fix                      # Auto-detect and fix permissions"
    echo "  $0 --fix --gid 998            # Fix with specific group ID"
}

# Function to detect Docker group ID
detect_docker_gid() {
    local docker_gid
    
    # Method 1: Check docker socket group
    if [ -S /var/run/docker.sock ]; then
        docker_gid=$(stat -c '%g' /var/run/docker.sock 2>/dev/null)
        if [ -n "$docker_gid" ] && [ "$docker_gid" != "0" ]; then
            echo "$docker_gid"
            return 0
        fi
    fi
    
    # Method 2: Check /etc/group
    docker_gid=$(getent group docker 2>/dev/null | cut -d: -f3)
    if [ -n "$docker_gid" ]; then
        echo "$docker_gid"
        return 0
    fi
    
    # Method 3: Check running Docker containers
    if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
        docker_gid=$(docker run --rm -v /var/run/docker.sock:/var/run/docker.sock alpine:latest stat -c '%g' /var/run/docker.sock 2>/dev/null || echo "")
        if [ -n "$docker_gid" ] && [ "$docker_gid" != "0" ]; then
            echo "$docker_gid"
            return 0
        fi
    fi
    
    # Default fallback
    echo "999"
}

# Function to check Docker permissions
check_permissions() {
    print_status "Checking Docker permissions..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        return 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker daemon is not running!"
        return 1
    fi
    
    # Check Docker socket
    if [ ! -S /var/run/docker.sock ]; then
        print_error "Docker socket not found at /var/run/docker.sock"
        return 1
    fi
    
    # Get socket permissions
    local socket_perms=$(ls -la /var/run/docker.sock)
    local socket_gid=$(stat -c '%g' /var/run/docker.sock)
    local socket_group=$(stat -c '%G' /var/run/docker.sock)
    
    print_status "Docker socket: $socket_perms"
    print_status "Socket group ID: $socket_gid"
    print_status "Socket group name: $socket_group"
    
    # Check if current user can access Docker
    if docker ps > /dev/null 2>&1; then
        print_success "Current user can access Docker daemon"
    else
        print_warning "Current user cannot access Docker daemon"
        print_status "User groups: $(groups)"
    fi
    
    # Detect Docker group ID
    local detected_gid=$(detect_docker_gid)
    print_status "Detected Docker group ID: $detected_gid"
    
    return 0
}

# Function to apply Docker permission fixes
apply_fixes() {
    local target_gid="$1"
    
    print_status "Applying Docker permission fixes..."
    
    if [ -z "$target_gid" ]; then
        target_gid=$(detect_docker_gid)
        print_status "Auto-detected Docker group ID: $target_gid"
    else
        print_status "Using specified Docker group ID: $target_gid"
    fi
    
    # Update .env file
    if [ -f .env ]; then
        print_status "Updating .env file..."
        if grep -q "DOCKER_GID=" .env; then
            sed -i.bak "s|DOCKER_GID=.*|DOCKER_GID=$target_gid|" .env
        else
            echo "DOCKER_GID=$target_gid" >> .env
        fi
        rm -f .env.bak
        print_success "Updated DOCKER_GID in .env file"
    else
        print_warning ".env file not found, creating from template..."
        if [ -f .env.example ]; then
            cp .env.example .env
            echo "DOCKER_GID=$target_gid" >> .env
            print_success "Created .env file with DOCKER_GID=$target_gid"
        else
            print_error ".env.example not found!"
            return 1
        fi
    fi
    
    # Verify docker-compose.yml has the necessary configuration
    if [ -f docker-compose.yml ]; then
        if grep -q "DOCKER_GID" docker-compose.yml; then
            print_success "docker-compose.yml already configured for Docker permissions"
        else
            print_warning "docker-compose.yml may need manual updates for Docker permissions"
            print_status "Please ensure your docker-compose.yml includes:"
            echo "  build:"
            echo "    args:"
            echo "      DOCKER_GID: \${DOCKER_GID:-999}"
            echo "  group_add:"
            echo "    - \${DOCKER_GID:-999}"
        fi
    else
        print_error "docker-compose.yml not found!"
        return 1
    fi
    
    # Detect Docker Compose command
    local compose_cmd="docker-compose"
    if ! command -v docker-compose &> /dev/null; then
        if docker compose version &> /dev/null 2>&1; then
            compose_cmd="docker compose"
        fi
    fi
    
    print_success "Docker permission fixes applied successfully!"
    print_status "Next steps:"
    echo "  1. Rebuild containers: $compose_cmd down && $compose_cmd up -d --build"
    echo "  2. Test Docker access: $compose_cmd exec script-executor docker ps"
    
    return 0
}

# Parse command line arguments
CHECK_ONLY=false
APPLY_FIX=false
CUSTOM_GID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --check)
            CHECK_ONLY=true
            shift
            ;;
        --fix)
            APPLY_FIX=true
            shift
            ;;
        --gid)
            CUSTOM_GID="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo "🔧 Docker Permission Fix Script"
    echo "==============================="
    
    if [ "$CHECK_ONLY" = true ]; then
        check_permissions
    elif [ "$APPLY_FIX" = true ]; then
        check_permissions
        echo ""
        apply_fixes "$CUSTOM_GID"
    else
        print_status "No action specified. Use --check or --fix"
        show_usage
        exit 1
    fi
}

# Run main function
main "$@"