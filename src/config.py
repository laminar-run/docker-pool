"""Configuration constants and settings for the Docker Pool Server."""

import os

# File upload configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file
MAX_TOTAL_SIZE = 50 * 1024 * 1024  # 50MB total
ALLOWED_EXTENSIONS = {
    'txt', 'py', 'js', 'html', 'css', 'json', 'xml', 'csv', 'md', 'yml', 'yaml',
    'sh', 'bat', 'sql', 'log', 'conf', 'cfg', 'ini', 'properties', 'dockerfile',
    'java', 'cpp', 'c', 'h', 'hpp', 'go', 'rs', 'php', 'rb', 'pl', 'r', 'scala'
}

# ZIP file security configuration
ZIP_SUPPORT_ENABLED = os.environ.get('ZIP_SUPPORT_ENABLED', 'false').lower() == 'true'
ZIP_MAX_EXTRACTED_SIZE = 100 * 1024 * 1024  # 100MB maximum extracted size
ZIP_MAX_FILES = 1000  # Maximum files per ZIP
ZIP_MAX_COMPRESSION_RATIO = 100  # Maximum compression ratio (1:100)
ZIP_EXTRACTION_TIMEOUT = 30  # Seconds
ZIP_MAX_NESTED_DEPTH = 3  # Maximum nested archive depth
ZIP_ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS.copy()  # Extensions allowed in ZIP files

# Add ZIP to allowed extensions when ZIP support is enabled
if ZIP_SUPPORT_ENABLED:
    ALLOWED_EXTENSIONS = ALLOWED_EXTENSIONS | {'zip'}

# Docker configuration
DEFAULT_DOCKER_SOCKETS = [
    "unix:///var/run/docker.sock",
    "unix:///Users/saheedakinbile/.docker/run/docker.sock"
]

# Container security settings
CONTAINER_SECURITY_CONFIG = {
    'network_disabled': True,
    'read_only': False,
    'tmpfs': {'/tmp': 'size=100M'},
    'security_opt': ["no-new-privileges"],
    'cap_drop': ["ALL"],
    'cap_add': ["CHOWN", "SETUID", "SETGID"],
}

# Default server configuration
DEFAULT_CONFIG = {
    "default_pool_size": int(os.environ.get('POOL_SIZE', 5)),
    "default_image": os.environ.get('BASE_IMAGE', 'alpine:latest'),
    "memory_limit": os.environ.get('MEMORY_LIMIT', '256m'),
    "cpu_limit": float(os.environ.get('CPU_LIMIT', 0.5)),
    "timeout": int(os.environ.get('TIMEOUT', 30)),
    "custom_image_registry": os.environ.get('CUSTOM_IMAGE_REGISTRY', ''),
    "custom_image_pull_timeout": int(os.environ.get('CUSTOM_IMAGE_PULL_TIMEOUT', 300)),
    "custom_image_pull_retries": int(os.environ.get('CUSTOM_IMAGE_PULL_RETRIES', 3)),
}

def parse_custom_pools() -> dict:
    """Parse custom pools configuration from environment."""
    custom_pools = {}
    custom_pools_env = os.environ.get('CUSTOM_POOLS', '')
    if custom_pools_env:
        # Format: "image1:size1,image2:size2"
        # Example: "python-scientific-executor:3,nodejs-executor:2"
        try:
            for pool_config in custom_pools_env.split(','):
                if ':' in pool_config:
                    image, size = pool_config.strip().split(':', 1)
                    custom_pools[image] = int(size)
        except Exception:
            pass  # Invalid configuration will be logged by caller
    return custom_pools