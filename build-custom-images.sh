#!/bin/bash

# Build script for custom container images
# This script builds all the custom images for the script execution server

set -e

echo "🐳 Building Custom Container Images for Script Execution Server"
echo "=============================================================="

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

# Function to build an image
build_image() {
    local image_dir=$1
    local image_name=$2
    local description=$3
    
    print_status "Building $description..."
    print_status "Directory: $image_dir"
    print_status "Image name: $image_name"
    
    if [ ! -d "$image_dir" ]; then
        print_error "Directory $image_dir does not exist!"
        return 1
    fi
    
    cd "$image_dir"
    
    if docker build -t "$image_name" .; then
        print_success "Successfully built $image_name"
        
        # Get image size
        local size=$(docker images "$image_name" --format "table {{.Size}}" | tail -n 1)
        print_status "Image size: $size"
        
        cd - > /dev/null
        return 0
    else
        print_error "Failed to build $image_name"
        cd - > /dev/null
        return 1
    fi
}

# Function to test an image
test_image() {
    local image_name=$1
    local test_command=$2
    
    print_status "Testing $image_name..."
    
    if docker run --rm "$image_name" /bin/sh -c "$test_command" > /dev/null 2>&1; then
        print_success "Test passed for $image_name"
        return 0
    else
        print_warning "Test failed for $image_name"
        return 1
    fi
}

# Main build process
main() {
    local build_all=true
    local test_images=false
    local push_images=false
    local registry=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --test)
                test_images=true
                shift
                ;;
            --push)
                push_images=true
                shift
                ;;
            --registry)
                registry="$2"
                shift 2
                ;;
            --python-only)
                build_all=false
                build_python=true
                shift
                ;;
            --nodejs-only)
                build_all=false
                build_nodejs=true
                shift
                ;;
            --multi-only)
                build_all=false
                build_multi=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --test          Test images after building"
                echo "  --push          Push images to registry"
                echo "  --registry REG  Registry to push to (e.g., my-registry.com)"
                echo "  --python-only   Build only Python scientific image"
                echo "  --nodejs-only   Build only Node.js image"
                echo "  --multi-only    Build only multi-language image"
                echo "  --help          Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0                                    # Build all images"
                echo "  $0 --test                            # Build and test all images"
                echo "  $0 --push --registry my-registry.com # Build and push to registry"
                echo "  $0 --python-only --test              # Build and test Python image only"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running or not accessible!"
        exit 1
    fi
    
    print_status "Starting build process..."
    
    local failed_builds=0
    local total_builds=0
    
    # Build Python Scientific Image
    if [ "$build_all" = true ] || [ "$build_python" = true ]; then
        total_builds=$((total_builds + 1))
        if build_image "custom-images/python-scientific" "python-scientific-executor" "Python Scientific Computing Environment"; then
            if [ "$test_images" = true ]; then
                test_image "python-scientific-executor" "python3 -c 'import numpy, pandas, scipy; print(\"All packages imported successfully\")'"
            fi
        else
            failed_builds=$((failed_builds + 1))
        fi
    fi
    
    # Build Node.js Image
    if [ "$build_all" = true ] || [ "$build_nodejs" = true ]; then
        total_builds=$((total_builds + 1))
        if build_image "custom-images/nodejs-runtime" "nodejs-executor" "Node.js Runtime Environment"; then
            if [ "$test_images" = true ]; then
                test_image "nodejs-executor" "node -e 'console.log(\"Node.js version:\", process.version)'"
            fi
        else
            failed_builds=$((failed_builds + 1))
        fi
    fi
    
    # Build Multi-language Image
    if [ "$build_all" = true ] || [ "$build_multi" = true ]; then
        total_builds=$((total_builds + 1))
        if build_image "custom-images/multi-language" "multi-language-executor" "Multi-Language Development Environment"; then
            if [ "$test_images" = true ]; then
                test_image "multi-language-executor" "python3 --version && node --version && java -version && go version"
            fi
        else
            failed_builds=$((failed_builds + 1))
        fi
    fi
    
    # Push images if requested
    if [ "$push_images" = true ] && [ -n "$registry" ]; then
        print_status "Pushing images to registry: $registry"
        
        for image in "python-scientific-executor" "nodejs-executor" "multi-language-executor"; do
            if docker images "$image" --format "{{.Repository}}" | grep -q "$image"; then
                local tagged_image="$registry/$image"
                print_status "Tagging and pushing $image as $tagged_image"
                
                if docker tag "$image" "$tagged_image" && docker push "$tagged_image"; then
                    print_success "Successfully pushed $tagged_image"
                else
                    print_error "Failed to push $tagged_image"
                fi
            fi
        done
    fi
    
    # Summary
    echo ""
    echo "=============================================================="
    print_status "Build Summary"
    echo "=============================================================="
    
    if [ $failed_builds -eq 0 ]; then
        print_success "All $total_builds images built successfully! 🎉"
    else
        print_warning "$failed_builds out of $total_builds builds failed"
    fi
    
    # Show built images
    echo ""
    print_status "Built Images:"
    docker images | grep -E "(python-scientific-executor|nodejs-executor|multi-language-executor)" || print_warning "No custom images found"
    
    echo ""
    print_status "Usage Examples:"
    echo "  BASE_IMAGE=python-scientific-executor docker-compose up -d"
    echo "  BASE_IMAGE=nodejs-executor docker-compose up -d"
    echo "  BASE_IMAGE=multi-language-executor docker-compose up -d"
    
    if [ $failed_builds -gt 0 ]; then
        exit 1
    fi
}

# Run main function
main "$@"