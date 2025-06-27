"""Docker utilities and helper functions."""

import docker
import os
import re
import time
import logging
from typing import Optional

from .config import DEFAULT_DOCKER_SOCKETS

logger = logging.getLogger(__name__)


def create_docker_client():
    """Create Docker client with fallback socket paths."""
    try:
        return docker.from_env()
    except Exception as e:
        # Try common Docker Desktop socket locations
        socket_paths = DEFAULT_DOCKER_SOCKETS + [
            f"unix://{os.path.expanduser('~')}/.docker/run/docker.sock"
        ]
        
        for socket_path in socket_paths:
            try:
                client = docker.DockerClient(base_url=socket_path)
                client.ping()  # Test connection
                logger.info(f"Connected to Docker using {socket_path}")
                return client
            except Exception:
                continue
        else:
            raise Exception(f"Could not connect to Docker daemon. Original error: {e}")


def validate_image_name(image_name: str) -> bool:
    """Validate Docker image name format."""
    pattern = r'^[a-z0-9]+(([._-])[a-z0-9]+)*(/[a-z0-9]+(([._-])[a-z0-9]+)*)*(:[\w][\w.-]{0,127})?$'
    return bool(re.match(pattern, image_name.lower()))


def pull_image_with_retry(client, image_name: str, retries: int = 3) -> bool:
    """Pull Docker image with retry logic."""
    if not validate_image_name(image_name):
        logger.error(f"Invalid image name format: {image_name}")
        return False
    
    for attempt in range(retries):
        try:
            logger.info(f"Pulling image {image_name} (attempt {attempt + 1}/{retries})")
            
            # Check if image already exists locally
            try:
                client.images.get(image_name)
                logger.info(f"Image {image_name} already exists locally")
                return True
            except docker.errors.ImageNotFound:
                pass
            
            # Pull the image
            client.images.pull(image_name)
            logger.info(f"Successfully pulled image: {image_name}")
            return True
            
        except docker.errors.APIError as e:
            logger.warning(f"Failed to pull image {image_name} (attempt {attempt + 1}): {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                logger.error(f"Failed to pull image {image_name} after {retries} attempts")
                return False
        except Exception as e:
            logger.error(f"Unexpected error pulling image {image_name}: {e}")
            return False
    
    return False


def execute_in_container(container, script: str, stdin: Optional[str], start_time: float) -> dict:
    """Execute script in the given container."""
    # Execute the entire script as one command to maintain state
    # Escape single quotes in the script
    escaped_script = script.replace("'", "'\"'\"'")
    
    # Execute the script as a single shell command
    result = container.exec_run(f"/bin/sh -c '{escaped_script}'")
    
    # Handle output
    stdout = ""
    stderr = ""
    
    if result.output:
        output = result.output
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace')
        stdout = output
    
    execution_time = time.time() - start_time
    
    return {
        "success": result.exit_code == 0,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": result.exit_code,
        "execution_time": execution_time,
        "error": None
    }


def create_container_config(image: str, workspace_dir: str, memory_limit: str,
                          cpu_limit: float, labels: dict) -> dict:
    """Create container configuration dictionary."""
    from .config import CONTAINER_SECURITY_CONFIG
    
    config = {
        'image': image,
        'command': "/bin/sh",
        'stdin_open': True,
        'tty': True,
        'mem_limit': memory_limit,
        'cpu_quota': int(cpu_limit * 100000),
        'cpu_period': 100000,
        'volumes': {workspace_dir: {'bind': '/workspace', 'mode': 'rw'}},
        'labels': labels,
        **CONTAINER_SECURITY_CONFIG
    }
    
    return config


def create_container(client, image: str, workspace_dir: str, memory_limit: str,
                    cpu_limit: float, labels: dict):
    """Create and start a container with the given configuration."""
    from .config import CONTAINER_SECURITY_CONFIG
    
    container = client.containers.create(
        image,
        command="/bin/sh",
        stdin_open=True,
        tty=True,
        mem_limit=memory_limit,
        cpu_quota=int(cpu_limit * 100000),
        cpu_period=100000,
        volumes={workspace_dir: {'bind': '/workspace', 'mode': 'rw'}},
        labels=labels,
        **CONTAINER_SECURITY_CONFIG
    )
    container.start()
    return container