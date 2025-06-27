"""Container pool management for Docker-based script execution."""

import os
import queue
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from typing import Dict, Optional
import logging

from .docker_utils import (
    create_docker_client,
    pull_image_with_retry,
    execute_in_container,
    create_container
)

logger = logging.getLogger(__name__)


class ContainerPool:
    """Manages a pool of Docker containers for executing untrusted scripts."""
    
    def __init__(self,
                 pool_size: int = 5,
                 base_image: str = "alpine:latest",
                 memory_limit: str = "256m",
                 cpu_limit: float = 0.5,
                 timeout: int = 30,
                 custom_image_registry: str = "",
                 custom_image_pull_timeout: int = 300,
                 custom_image_pull_retries: int = 3,
                 pool_name: str = "default"):
        self.pool_size = pool_size
        self.base_image = base_image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.timeout = timeout
        self.custom_image_registry = custom_image_registry
        self.custom_image_pull_timeout = custom_image_pull_timeout
        self.custom_image_pull_retries = custom_image_pull_retries
        self.pool_name = pool_name
        
        # Connect to Docker
        self.client = create_docker_client()
        
        self.available_containers = queue.Queue()
        self.container_lock = threading.Lock()
        self.shutdown = False
        
        # Metrics
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0,
            "containers_created": 0,
            "containers_destroyed": 0
        }
        
        # Start pool maintenance thread
        self.maintenance_thread = threading.Thread(target=self._maintain_pool, daemon=True)
        self.maintenance_thread.start()
        
        # Validate and prepare the base image
        self._prepare_base_image()
        
        # Initialize the pool
        self._initialize_pool()
    
    def _prepare_base_image(self):
        """Prepare and validate the base image."""
        logger.info(f"Preparing base image: {self.base_image}")
        
        # If custom registry is specified, prepend it to the image name
        if self.custom_image_registry and not self.base_image.startswith(self.custom_image_registry):
            full_image_name = f"{self.custom_image_registry}/{self.base_image}"
        else:
            full_image_name = self.base_image
        
        # Try to pull the image
        if not pull_image_with_retry(self.client, full_image_name, self.custom_image_pull_retries):
            logger.warning(f"Could not pull custom image {full_image_name}, falling back to alpine:latest")
            self.base_image = "alpine:latest"
            if not pull_image_with_retry(self.client, self.base_image, self.custom_image_pull_retries):
                raise RuntimeError(f"Could not pull fallback image: {self.base_image}")
        else:
            self.base_image = full_image_name
        
        logger.info(f"Using base image: {self.base_image}")
    
    def _initialize_pool(self):
        """Create initial containers for the pool."""
        logger.info(f"Initializing container pool with {self.pool_size} containers")
        for _ in range(self.pool_size):
            self._create_container()
    
    def _create_container(self):
        """Create a new container and add it to the pool."""
        try:
            # Create unique workspace directory for this container
            workspace_dir = tempfile.mkdtemp(prefix='docker_workspace_')
            
            labels = {
                "pool": "script-executor",
                "status": "available",
                "workspace": workspace_dir
            }
            
            container = create_container(
                self.client, self.base_image, workspace_dir,
                self.memory_limit, self.cpu_limit, labels
            )
            
            # Store workspace directory reference with container
            container.workspace_dir = workspace_dir
            
            self.available_containers.put(container)
            self.metrics["containers_created"] += 1
            logger.info(f"Created container {container.short_id} with workspace {workspace_dir}")
        except Exception as e:
            logger.error(f"Failed to create container: {e}")
    
    def _maintain_pool(self):
        """Background thread to maintain pool size."""
        while not self.shutdown:
            try:
                current_size = self.available_containers.qsize()
                if current_size < self.pool_size:
                    logger.info(f"Pool size ({current_size}) below target ({self.pool_size}), creating containers")
                    for _ in range(self.pool_size - current_size):
                        self._create_container()
            except Exception as e:
                logger.error(f"Pool maintenance error: {e}")
            
            time.sleep(5)
    
    @contextmanager
    def get_container(self):
        """Get a container from the pool. Container is destroyed after use."""
        container = None
        try:
            container = self.available_containers.get(timeout=30)
            logger.info(f"Acquired container {container.short_id}")
            yield container
        except queue.Empty:
            logger.error("No containers available in pool")
            raise RuntimeError("No containers available")
        finally:
            if container:
                try:
                    # Clean up workspace directory if it exists
                    if hasattr(container, 'workspace_dir') and os.path.exists(container.workspace_dir):
                        try:
                            shutil.rmtree(container.workspace_dir)
                            logger.info(f"Cleaned up workspace: {container.workspace_dir}")
                        except Exception as e:
                            logger.error(f"Failed to cleanup workspace {container.workspace_dir}: {e}")
                    
                    container.stop(timeout=5)
                    container.remove(force=True)
                    self.metrics["containers_destroyed"] += 1
                    logger.info(f"Destroyed container {container.short_id}")
                except Exception as e:
                    logger.error(f"Failed to destroy container: {e}")
    
    def execute_script(self, script: str, stdin: Optional[str] = None, custom_image: Optional[str] = None,
                      session_id: Optional[str] = None, file_manager=None) -> Dict[str, any]:
        """Execute a script in a container from the pool or custom image."""
        start_time = time.time()
        self.metrics["total_executions"] += 1
        
        try:
            # Use custom image if specified, otherwise use pool container
            if custom_image:
                return self._execute_with_custom_image(script, stdin, custom_image, start_time, session_id, file_manager)
            else:
                return self._execute_with_pool_container(script, stdin, start_time, session_id, file_manager)
                
        except Exception as e:
            self.metrics["failed_executions"] += 1
            execution_time = time.time() - start_time
            
            # Ensure error message is always a string
            error_msg = str(e)
            
            logger.error(f"Script execution failed: {error_msg}")
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg,
                "exit_code": -1,
                "execution_time": execution_time,
                "error": error_msg
            }
    
    def _execute_with_pool_container(self, script: str, stdin: Optional[str], start_time: float,
                                   session_id: Optional[str] = None, file_manager=None) -> Dict[str, any]:
        """Execute script using a container from the pool."""
        with self.get_container() as container:
            # Copy files to container workspace if session provided
            if session_id and file_manager and hasattr(container, 'workspace_dir'):
                if not file_manager.copy_files_to_container_workspace(session_id, container.workspace_dir):
                    logger.warning(f"Failed to copy files for session {session_id}")
            
            result = execute_in_container(container, script, stdin, start_time)
            
            # Update metrics
            if result["success"]:
                self.metrics["successful_executions"] += 1
            else:
                self.metrics["failed_executions"] += 1
                
            self.metrics["average_execution_time"] = (
                (self.metrics["average_execution_time"] * (self.metrics["total_executions"] - 1) + result["execution_time"])
                / self.metrics["total_executions"]
            )
            
            return result
    
    def _execute_with_custom_image(self, script: str, stdin: Optional[str], custom_image: str, start_time: float,
                                 session_id: Optional[str] = None, file_manager=None) -> Dict[str, any]:
        """Execute script using a custom image (creates temporary container)."""
        from .docker_utils import validate_image_name
        
        # Validate and prepare custom image
        if not validate_image_name(custom_image):
            raise ValueError(f"Invalid custom image name: {custom_image}")
        
        # Add registry prefix if configured
        if self.custom_image_registry and not custom_image.startswith(self.custom_image_registry):
            full_image_name = f"{self.custom_image_registry}/{custom_image}"
        else:
            full_image_name = custom_image
        
        # Pull image if needed
        if not pull_image_with_retry(self.client, full_image_name, self.custom_image_pull_retries):
            raise RuntimeError(f"Failed to pull custom image: {full_image_name}")
        
        # Create workspace directory for this container
        workspace_dir = tempfile.mkdtemp(prefix='docker_workspace_custom_')
        
        # Create temporary container with custom image
        container = None
        try:
            labels = {
                "pool": "script-executor",
                "status": "custom",
                "image": full_image_name,
                "workspace": workspace_dir
            }
            
            container = create_container(
                self.client, full_image_name, workspace_dir,
                self.memory_limit, self.cpu_limit, labels
            )
            logger.info(f"Created custom container {container.short_id} with image {full_image_name} and workspace {workspace_dir}")
            
            # Copy files to container workspace if session provided
            if session_id and file_manager:
                if not file_manager.copy_files_to_container_workspace(session_id, workspace_dir):
                    logger.warning(f"Failed to copy files for session {session_id}")
            
            return execute_in_container(container, script, stdin, start_time)
            
        finally:
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.info(f"Destroyed custom container {container.short_id}")
                except Exception as e:
                    logger.error(f"Failed to destroy custom container: {e}")
            
            # Clean up workspace directory
            if os.path.exists(workspace_dir):
                try:
                    shutil.rmtree(workspace_dir)
                    logger.info(f"Cleaned up custom workspace: {workspace_dir}")
                except Exception as e:
                    logger.error(f"Failed to cleanup custom workspace {workspace_dir}: {e}")
    
    def get_metrics(self):
        """Get pool metrics."""
        return {
            **self.metrics,
            "pool_size": self.pool_size,
            "available_containers": self.available_containers.qsize()
        }
    
    def shutdown_pool(self):
        """Shutdown the container pool and clean up resources."""
        logger.info("Shutting down container pool")
        self.shutdown = True
        
        while not self.available_containers.empty():
            try:
                container = self.available_containers.get_nowait()
                # Clean up workspace directory if it exists
                if hasattr(container, 'workspace_dir') and os.path.exists(container.workspace_dir):
                    try:
                        shutil.rmtree(container.workspace_dir)
                        logger.info(f"Cleaned up workspace: {container.workspace_dir}")
                    except Exception as e:
                        logger.error(f"Failed to cleanup workspace {container.workspace_dir}: {e}")
                
                container.stop(timeout=5)
                container.remove(force=True)
            except:
                pass
        
        for container in self.client.containers.list(all=True, filters={"label": "pool=script-executor"}):
            try:
                # Try to get workspace from labels and clean up
                workspace_dir = container.labels.get('workspace')
                if workspace_dir and os.path.exists(workspace_dir):
                    try:
                        shutil.rmtree(workspace_dir)
                        logger.info(f"Cleaned up workspace: {workspace_dir}")
                    except Exception as e:
                        logger.error(f"Failed to cleanup workspace {workspace_dir}: {e}")
                
                container.stop(timeout=5)
                container.remove(force=True)
            except:
                pass