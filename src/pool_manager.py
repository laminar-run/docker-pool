"""Multi-pool manager for handling different container images."""

import tempfile
import time
from typing import Dict, Optional
import logging

from .container_pool import ContainerPool
from .docker_utils import create_docker_client, pull_image_with_retry, validate_image_name, execute_in_container

logger = logging.getLogger(__name__)


class MultiPoolManager:
    """Manages multiple container pools for different images."""
    
    def __init__(self,
                 default_pool_size: int = 5,
                 default_image: str = "alpine:latest",
                 memory_limit: str = "256m",
                 cpu_limit: float = 0.5,
                 timeout: int = 30,
                 custom_image_registry: str = "",
                 custom_image_pull_timeout: int = 300,
                 custom_image_pull_retries: int = 3,
                 custom_pools: Dict[str, int] = None):
        
        self.default_pool_size = default_pool_size
        self.default_image = default_image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.timeout = timeout
        self.custom_image_registry = custom_image_registry
        self.custom_image_pull_timeout = custom_image_pull_timeout
        self.custom_image_pull_retries = custom_image_pull_retries
        
        # Dictionary to store multiple pools: {image_name: ContainerPool}
        self.pools = {}
        
        # Custom pools configuration: {image_name: pool_size}
        self.custom_pools_config = custom_pools or {}
        
        # Combined metrics across all pools
        self.global_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0,
            "containers_created": 0,
            "containers_destroyed": 0,
            "pools_active": 0
        }
        
        self.shutdown = False
        
        # Initialize pools
        self._initialize_pools()
    
    def _initialize_pools(self):
        """Initialize all configured pools."""
        logger.info("Initializing container pools...")
        
        # Create default pool
        logger.info(f"Creating default pool with image: {self.default_image}")
        self.pools[self.default_image] = ContainerPool(
            pool_size=self.default_pool_size,
            base_image=self.default_image,
            memory_limit=self.memory_limit,
            cpu_limit=self.cpu_limit,
            timeout=self.timeout,
            custom_image_registry=self.custom_image_registry,
            custom_image_pull_timeout=self.custom_image_pull_timeout,
            custom_image_pull_retries=self.custom_image_pull_retries,
            pool_name="default"
        )
        
        # Create custom pools
        for image_name, pool_size in self.custom_pools_config.items():
            logger.info(f"Creating custom pool for image: {image_name} (size: {pool_size})")
            self.pools[image_name] = ContainerPool(
                pool_size=pool_size,
                base_image=image_name,
                memory_limit=self.memory_limit,
                cpu_limit=self.cpu_limit,
                timeout=self.timeout,
                custom_image_registry=self.custom_image_registry,
                custom_image_pull_timeout=self.custom_image_pull_timeout,
                custom_image_pull_retries=self.custom_image_pull_retries,
                pool_name=f"custom-{image_name.replace(':', '-').replace('/', '-')}"
            )
        
        self.global_metrics["pools_active"] = len(self.pools)
        logger.info(f"Initialized {len(self.pools)} container pools")
    
    def execute_script(self, script: str, stdin: Optional[str] = None, custom_image: Optional[str] = None,
                      session_id: Optional[str] = None, file_manager=None) -> Dict[str, any]:
        """Execute a script using the appropriate pool or creating a temporary container."""
        start_time = time.time()
        self.global_metrics["total_executions"] += 1
        
        try:
            # Determine which image to use
            target_image = custom_image or self.default_image
            
            # Check if we have a pool for this image
            if target_image in self.pools:
                logger.info(f"Using pool for image: {target_image}")
                result = self.pools[target_image].execute_script(script, stdin, None, session_id, file_manager)
            else:
                logger.info(f"No pool available for {target_image}, creating temporary container")
                result = self._execute_with_temporary_container(script, stdin, target_image, start_time, session_id, file_manager)
            
            # Update global metrics
            if result.get("success"):
                self.global_metrics["successful_executions"] += 1
            else:
                self.global_metrics["failed_executions"] += 1
            
            execution_time = result.get("execution_time", time.time() - start_time)
            self.global_metrics["average_execution_time"] = (
                (self.global_metrics["average_execution_time"] * (self.global_metrics["total_executions"] - 1) + execution_time)
                / self.global_metrics["total_executions"]
            )
            
            return result
            
        except Exception as e:
            self.global_metrics["failed_executions"] += 1
            execution_time = time.time() - start_time
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
    
    def _execute_with_temporary_container(self, script: str, stdin: Optional[str], image: str, start_time: float,
                                        session_id: Optional[str] = None, file_manager=None) -> Dict[str, any]:
        """Execute script using a temporary container (fallback when no pool exists)."""
        from .docker_utils import create_container
        import shutil
        import os
        
        # Validate image name
        if not validate_image_name(image):
            raise ValueError(f"Invalid image name: {image}")
        
        # Add registry prefix if configured
        if self.custom_image_registry and not image.startswith(self.custom_image_registry):
            full_image_name = f"{self.custom_image_registry}/{image}"
        else:
            full_image_name = image
        
        # Pull image if needed
        client = create_docker_client()
        if not pull_image_with_retry(client, full_image_name, self.custom_image_pull_retries):
            raise RuntimeError(f"Failed to pull image: {full_image_name}")
        
        # Create workspace directory for this container
        workspace_dir = tempfile.mkdtemp(prefix='docker_workspace_temp_')
        
        # Create temporary container
        container = None
        try:
            labels = {
                "pool": "script-executor",
                "status": "temporary",
                "image": full_image_name,
                "workspace": workspace_dir
            }
            
            container = create_container(
                client, full_image_name, workspace_dir,
                self.memory_limit, self.cpu_limit, labels
            )
            logger.info(f"Created temporary container {container.short_id} with image {full_image_name} and workspace {workspace_dir}")
            
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
                    logger.info(f"Destroyed temporary container {container.short_id}")
                except Exception as e:
                    logger.error(f"Failed to destroy temporary container: {e}")
            
            # Clean up workspace directory
            if os.path.exists(workspace_dir):
                try:
                    shutil.rmtree(workspace_dir)
                    logger.info(f"Cleaned up temporary workspace: {workspace_dir}")
                except Exception as e:
                    logger.error(f"Failed to cleanup temporary workspace {workspace_dir}: {e}")
    
    def get_metrics(self):
        """Get combined metrics from all pools."""
        pool_metrics = {}
        total_available = 0
        
        for image, pool in self.pools.items():
            pool_stats = pool.get_metrics()
            pool_metrics[image] = pool_stats
            total_available += pool_stats.get("available_containers", 0)
        
        return {
            **self.global_metrics,
            "total_available_containers": total_available,
            "pool_metrics": pool_metrics
        }
    
    def shutdown_pools(self):
        """Shutdown all container pools."""
        logger.info("Shutting down all container pools")
        self.shutdown = True
        
        for image, pool in self.pools.items():
            logger.info(f"Shutting down pool for {image}")
            pool.shutdown_pool()