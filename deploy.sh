#!/bin/bash

# Production deployment script for Docker Script Execution Server
# This script handles the complete deployment process

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

# Default values
ENVIRONMENT="production"
BUILD_IMAGES=false
CUSTOM_IMAGE=""
REGISTRY=""
SKIP_TESTS=false

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --env ENV           Environment (production|development) [default: production]"
    echo "  --build-images      Build custom images before deployment"
    echo "  --custom-image IMG  Use specific custom image"
    echo "  --registry REG      Docker registry for custom images"
    echo "  --skip-tests        Skip health checks after deployment"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                          # Basic production deployment"
    echo "  $0 --env development                        # Development deployment"
    echo "  $0 --build-images --custom-image python-scientific-executor"
    echo "  $0 --registry my-registry.com --custom-image my-custom-executor"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --build-images)
            BUILD_IMAGES=true
            shift
            ;;
        --custom-image)
            CUSTOM_IMAGE="$2"
            shift 2
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
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

# Function to detect Docker group ID
detect_docker_gid() {
    print_status "Detecting Docker group ID..."
    
    local docker_gid
    if [ -S /var/run/docker.sock ]; then
        # Get the group ID of the docker socket
        docker_gid=$(stat -c '%g' /var/run/docker.sock 2>/dev/null)
        if [ -n "$docker_gid" ] && [ "$docker_gid" != "0" ]; then
            print_success "Detected Docker group ID: $docker_gid"
            echo "$docker_gid"
            return 0
        fi
    fi
    
    # Fallback: try to get docker group ID from /etc/group
    docker_gid=$(getent group docker 2>/dev/null | cut -d: -f3)
    if [ -n "$docker_gid" ]; then
        print_success "Found Docker group ID from /etc/group: $docker_gid"
        echo "$docker_gid"
        return 0
    fi
    
    # Final fallback: use common default
    print_warning "Could not detect Docker group ID, using default: 999"
    echo "999"
}

# Function to detect Docker Compose command
detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null 2>&1; then
        echo "docker compose"
    else
        echo ""
    fi
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed!"
        print_status "Please install Docker first:"
        print_status "  Ubuntu/Debian: curl -fsSL https://get.docker.com | sh"
        print_status "  Or visit: https://docs.docker.com/engine/install/"
        exit 1
    fi
    
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker daemon is not running!"
        print_status "Start Docker with: sudo systemctl start docker"
        exit 1
    fi
    
    # Check Docker Compose
    DOCKER_COMPOSE_CMD=$(detect_docker_compose)
    if [ -z "$DOCKER_COMPOSE_CMD" ]; then
        print_error "Docker Compose is not available!"
        print_status "Install options:"
        print_status "  1. Docker Compose V2 (recommended): Already included with modern Docker"
        print_status "  2. Docker Compose V1: sudo apt-get install docker-compose"
        print_status "  3. Manual install: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    print_success "Prerequisites check passed"
    print_status "Using Docker Compose command: $DOCKER_COMPOSE_CMD"
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment for: $ENVIRONMENT"
    
    # Create .env file if it doesn't exist
    if [ ! -f .env ]; then
        print_status "Creating .env file from template..."
        cp .env.example .env
    fi
    
    # Detect and set Docker group ID
    local docker_gid=$(detect_docker_gid)
    print_status "Setting Docker group ID: $docker_gid"
    if grep -q "DOCKER_GID=" .env; then
        sed -i.bak "s|DOCKER_GID=.*|DOCKER_GID=$docker_gid|" .env
    else
        echo "DOCKER_GID=$docker_gid" >> .env
    fi
    rm -f .env.bak
    
    # Update environment-specific settings
    if [ "$ENVIRONMENT" = "development" ]; then
        sed -i.bak 's/FLASK_ENV=production/FLASK_ENV=development/' .env
        sed -i.bak 's/LOG_LEVEL=INFO/LOG_LEVEL=DEBUG/' .env
        rm -f .env.bak
    fi
    
    # Set custom image if specified
    if [ -n "$CUSTOM_IMAGE" ]; then
        print_status "Setting custom image: $CUSTOM_IMAGE"
        if grep -q "BASE_IMAGE=" .env; then
            sed -i.bak "s|BASE_IMAGE=.*|BASE_IMAGE=$CUSTOM_IMAGE|" .env
        else
            echo "BASE_IMAGE=$CUSTOM_IMAGE" >> .env
        fi
        rm -f .env.bak
    fi
    
    # Set registry if specified
    if [ -n "$REGISTRY" ]; then
        print_status "Setting custom registry: $REGISTRY"
        if grep -q "CUSTOM_IMAGE_REGISTRY=" .env; then
            sed -i.bak "s|CUSTOM_IMAGE_REGISTRY=.*|CUSTOM_IMAGE_REGISTRY=$REGISTRY|" .env
        else
            echo "CUSTOM_IMAGE_REGISTRY=$REGISTRY" >> .env
        fi
        rm -f .env.bak
    fi
    
    print_success "Environment setup completed"
}

# Function to build custom images
build_custom_images() {
    if [ "$BUILD_IMAGES" = true ]; then
        print_status "Building custom images..."
        
        if [ -x "./build-custom-images.sh" ]; then
            ./build-custom-images.sh --test
        else
            print_error "build-custom-images.sh not found or not executable!"
            exit 1
        fi
        
        print_success "Custom images built successfully"
    fi
}

# Function to deploy the application
deploy_application() {
    print_status "Deploying application..."
    
    # Stop existing containers
    print_status "Stopping existing containers..."
    $DOCKER_COMPOSE_CMD down --remove-orphans || true
    
    # Build and start new containers
    print_status "Building and starting containers..."
    $DOCKER_COMPOSE_CMD up -d --build
    
    print_success "Application deployed successfully"
}

# Function to wait for service to be ready
wait_for_service() {
    print_status "Waiting for service to be ready..."
    
    local max_attempts=30
    local attempt=1
    local port=$(grep HOST_PORT .env | cut -d'=' -f2 || echo "8080")
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f -s "http://localhost:$port/health" > /dev/null 2>&1; then
            print_success "Service is ready!"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts - waiting for service..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "Service failed to start within expected time"
    return 1
}

# Function to run health checks
run_health_checks() {
    if [ "$SKIP_TESTS" = true ]; then
        print_warning "Skipping health checks as requested"
        return 0
    fi
    
    print_status "Running health checks..."
    
    local port=$(grep HOST_PORT .env | cut -d'=' -f2 || echo "8080")
    local base_url="http://localhost:$port"
    
    # Health check
    print_status "Testing health endpoint..."
    if curl -f -s "$base_url/health" | grep -q "healthy"; then
        print_success "Health check passed"
    else
        print_error "Health check failed"
        return 1
    fi
    
    # Metrics check
    print_status "Testing metrics endpoint..."
    if curl -f -s "$base_url/metrics" | grep -q "pool_size"; then
        print_success "Metrics check passed"
    else
        print_error "Metrics check failed"
        return 1
    fi
    
    # Basic execution test
    print_status "Testing script execution..."
    local test_response=$(curl -f -s -X POST "$base_url/execute" \
        -H "Content-Type: application/json" \
        -d '{"script": "echo \"Deployment test successful\""}')
    
    if echo "$test_response" | grep -q "success.*true"; then
        print_success "Script execution test passed"
    else
        print_error "Script execution test failed"
        print_error "Response: $test_response"
        return 1
    fi
    
    print_success "All health checks passed!"
}

# Function to show deployment summary
show_summary() {
    print_status "Deployment Summary"
    echo "=================="
    
    local port=$(grep HOST_PORT .env | cut -d'=' -f2 || echo "8080")
    local base_image=$(grep BASE_IMAGE .env | cut -d'=' -f2 || echo "alpine:latest")
    
    echo "Environment: $ENVIRONMENT"
    echo "Base Image: $base_image"
    echo "Port: $port"
    echo "Service URL: http://localhost:$port"
    echo ""
    echo "Available Endpoints:"
    echo "  Health Check: http://localhost:$port/health"
    echo "  Metrics:      http://localhost:$port/metrics"
    echo "  Execute:      http://localhost:$port/execute (POST)"
    echo ""
    echo "Management Commands:"
    echo "  View logs:    $DOCKER_COMPOSE_CMD logs -f"
    echo "  Stop service: $DOCKER_COMPOSE_CMD down"
    echo "  Restart:      $DOCKER_COMPOSE_CMD restart"
    echo ""
    
    if [ -f "test_comprehensive.py" ]; then
        echo "Run comprehensive tests:"
        echo "  python test_comprehensive.py"
    fi
}

# Main deployment function
main() {
    echo "🚀 Docker Script Execution Server Deployment"
    echo "============================================="
    
    check_prerequisites
    setup_environment
    build_custom_images
    deploy_application
    
    if wait_for_service; then
        run_health_checks
        print_success "Deployment completed successfully! 🎉"
        show_summary
    else
        print_error "Deployment failed - service not ready"
        print_status "Checking container logs..."
        $DOCKER_COMPOSE_CMD logs --tail=20
        exit 1
    fi
}

# Run main function
main "$@"