# server.py
import docker
import threading
import queue
import time
import tempfile
import os
import re
from contextlib import contextmanager
from typing import Dict, Optional, List
import logging
from flask import Flask, request, jsonify

# Configure logging
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
    
    def execute_script(self, script: str, stdin: Optional[str] = None, custom_image: Optional[str] = None) -> Dict[str, any]:
        """Execute a script using the appropriate pool or creating a temporary container."""
        start_time = time.time()
        self.global_metrics["total_executions"] += 1
        
        try:
            # Determine which image to use
            target_image = custom_image or self.default_image
            
            # Check if we have a pool for this image
            if target_image in self.pools:
                logger.info(f"Using pool for image: {target_image}")
                result = self.pools[target_image].execute_script(script, stdin)
            else:
                logger.info(f"No pool available for {target_image}, creating temporary container")
                result = self._execute_with_temporary_container(script, stdin, target_image, start_time)
            
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
    
    def _execute_with_temporary_container(self, script: str, stdin: Optional[str], image: str, start_time: float) -> Dict[str, any]:
        """Execute script using a temporary container (fallback when no pool exists)."""
        # This is similar to the previous custom image execution logic
        if not self._validate_image_name(image):
            raise ValueError(f"Invalid image name: {image}")
        
        # Add registry prefix if configured
        if self.custom_image_registry and not image.startswith(self.custom_image_registry):
            full_image_name = f"{self.custom_image_registry}/{image}"
        else:
            full_image_name = image
        
        # Pull image if needed
        if not self._pull_image_with_retry(full_image_name):
            raise RuntimeError(f"Failed to pull image: {full_image_name}")
        
        # Create temporary container
        container = None
        try:
            container = self._create_docker_client().containers.create(
                full_image_name,
                command="/bin/sh",
                stdin_open=True,
                tty=True,
                mem_limit=self.memory_limit,
                cpu_quota=int(self.cpu_limit * 100000),
                cpu_period=100000,
                network_disabled=True,
                read_only=False,
                tmpfs={'/tmp': 'size=100M'},
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                cap_add=["CHOWN", "SETUID", "SETGID"],
                labels={"pool": "script-executor", "status": "temporary", "image": full_image_name}
            )
            container.start()
            logger.info(f"Created temporary container {container.short_id} with image {full_image_name}")
            
            return self._execute_in_container(container, script, stdin, start_time)
            
        finally:
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.info(f"Destroyed temporary container {container.short_id}")
                except Exception as e:
                    logger.error(f"Failed to destroy temporary container: {e}")
    
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
    
    def _create_docker_client(self):
        """Create Docker client (reuse logic from ContainerPool)."""
        try:
            return docker.from_env()
        except Exception as e:
            socket_paths = [
                "unix:///var/run/docker.sock",
                f"unix://{os.path.expanduser('~')}/.docker/run/docker.sock",
                "unix:///Users/saheedakinbile/.docker/run/docker.sock"
            ]
            
            for socket_path in socket_paths:
                try:
                    client = docker.DockerClient(base_url=socket_path)
                    client.ping()
                    return client
                except Exception:
                    continue
            else:
                raise Exception(f"Could not connect to Docker daemon. Original error: {e}")
    
    def _validate_image_name(self, image_name: str) -> bool:
        """Validate Docker image name format."""
        pattern = r'^[a-z0-9]+(([._-])[a-z0-9]+)*(/[a-z0-9]+(([._-])[a-z0-9]+)*)*(:[\w][\w.-]{0,127})?$'
        return bool(re.match(pattern, image_name.lower()))
    
    def _pull_image_with_retry(self, image_name: str) -> bool:
        """Pull Docker image with retry logic."""
        client = self._create_docker_client()
        
        for attempt in range(self.custom_image_pull_retries):
            try:
                logger.info(f"Pulling image {image_name} (attempt {attempt + 1}/{self.custom_image_pull_retries})")
                
                try:
                    client.images.get(image_name)
                    logger.info(f"Image {image_name} already exists locally")
                    return True
                except docker.errors.ImageNotFound:
                    pass
                
                client.images.pull(image_name)
                logger.info(f"Successfully pulled image: {image_name}")
                return True
                
            except docker.errors.APIError as e:
                logger.warning(f"Failed to pull image {image_name} (attempt {attempt + 1}): {e}")
                if attempt < self.custom_image_pull_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Failed to pull image {image_name} after {self.custom_image_pull_retries} attempts")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error pulling image {image_name}: {e}")
                return False
        
        return False
    
    def _execute_in_container(self, container, script: str, stdin: Optional[str], start_time: float) -> Dict[str, any]:
        """Execute script in the given container."""
        escaped_script = script.replace("'", "'\"'\"'")
        result = container.exec_run(f"/bin/sh -c '{escaped_script}'")
        
        stdout = ""
        if result.output:
            output = result.output
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='replace')
            stdout = output
        
        execution_time = time.time() - start_time
        
        return {
            "success": result.exit_code == 0,
            "stdout": stdout,
            "stderr": "",
            "exit_code": result.exit_code,
            "execution_time": execution_time,
            "error": None
        }


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
        
        # Try to connect to Docker with fallback socket paths
        try:
            self.client = docker.from_env()
        except Exception as e:
            # Try common Docker Desktop socket locations
            socket_paths = [
                "unix:///var/run/docker.sock",
                f"unix://{os.path.expanduser('~')}/.docker/run/docker.sock",
                "unix:///Users/saheedakinbile/.docker/run/docker.sock"
            ]
            
            for socket_path in socket_paths:
                try:
                    self.client = docker.DockerClient(base_url=socket_path)
                    self.client.ping()  # Test connection
                    logger.info(f"Connected to Docker using {socket_path}")
                    break
                except Exception:
                    continue
            else:
                raise Exception(f"Could not connect to Docker daemon. Original error: {e}")
        
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
    
    def _validate_image_name(self, image_name: str) -> bool:
        """Validate Docker image name format."""
        # Basic validation for Docker image names
        pattern = r'^[a-z0-9]+(([._-])[a-z0-9]+)*(/[a-z0-9]+(([._-])[a-z0-9]+)*)*(:[\w][\w.-]{0,127})?$'
        return bool(re.match(pattern, image_name.lower()))
    
    def _pull_image_with_retry(self, image_name: str) -> bool:
        """Pull Docker image with retry logic."""
        if not self._validate_image_name(image_name):
            logger.error(f"Invalid image name format: {image_name}")
            return False
        
        for attempt in range(self.custom_image_pull_retries):
            try:
                logger.info(f"Pulling image {image_name} (attempt {attempt + 1}/{self.custom_image_pull_retries})")
                
                # Check if image already exists locally
                try:
                    self.client.images.get(image_name)
                    logger.info(f"Image {image_name} already exists locally")
                    return True
                except docker.errors.ImageNotFound:
                    pass
                
                # Pull the image
                self.client.images.pull(image_name)
                logger.info(f"Successfully pulled image: {image_name}")
                return True
                
            except docker.errors.APIError as e:
                logger.warning(f"Failed to pull image {image_name} (attempt {attempt + 1}): {e}")
                if attempt < self.custom_image_pull_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to pull image {image_name} after {self.custom_image_pull_retries} attempts")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error pulling image {image_name}: {e}")
                return False
        
        return False
    
    def _prepare_base_image(self):
        """Prepare and validate the base image."""
        logger.info(f"Preparing base image: {self.base_image}")
        
        # If custom registry is specified, prepend it to the image name
        if self.custom_image_registry and not self.base_image.startswith(self.custom_image_registry):
            full_image_name = f"{self.custom_image_registry}/{self.base_image}"
        else:
            full_image_name = self.base_image
        
        # Try to pull the image
        if not self._pull_image_with_retry(full_image_name):
            logger.warning(f"Could not pull custom image {full_image_name}, falling back to alpine:latest")
            self.base_image = "alpine:latest"
            if not self._pull_image_with_retry(self.base_image):
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
            container = self.client.containers.create(
                self.base_image,
                command="/bin/sh",
                stdin_open=True,
                tty=True,
                mem_limit=self.memory_limit,
                cpu_quota=int(self.cpu_limit * 100000),
                cpu_period=100000,
                network_disabled=True,
                read_only=False,
                tmpfs={'/tmp': 'size=100M'},
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                cap_add=["CHOWN", "SETUID", "SETGID"],
                labels={"pool": "script-executor", "status": "available"}
            )
            container.start()
            self.available_containers.put(container)
            self.metrics["containers_created"] += 1
            logger.info(f"Created container {container.short_id}")
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
                    container.stop(timeout=5)
                    container.remove(force=True)
                    self.metrics["containers_destroyed"] += 1
                    logger.info(f"Destroyed container {container.short_id}")
                except Exception as e:
                    logger.error(f"Failed to destroy container: {e}")
    
    def execute_script(self, script: str, stdin: Optional[str] = None, custom_image: Optional[str] = None) -> Dict[str, any]:
        """Execute a script in a container from the pool or custom image."""
        start_time = time.time()
        self.metrics["total_executions"] += 1
        
        try:
            # Use custom image if specified, otherwise use pool container
            if custom_image:
                return self._execute_with_custom_image(script, stdin, custom_image, start_time)
            else:
                return self._execute_with_pool_container(script, stdin, start_time)
                
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
    
    def _execute_with_pool_container(self, script: str, stdin: Optional[str], start_time: float) -> Dict[str, any]:
        """Execute script using a container from the pool."""
        with self.get_container() as container:
            return self._execute_in_container(container, script, stdin, start_time)
    
    def _execute_with_custom_image(self, script: str, stdin: Optional[str], custom_image: str, start_time: float) -> Dict[str, any]:
        """Execute script using a custom image (creates temporary container)."""
        # Validate and prepare custom image
        if not self._validate_image_name(custom_image):
            raise ValueError(f"Invalid custom image name: {custom_image}")
        
        # Add registry prefix if configured
        if self.custom_image_registry and not custom_image.startswith(self.custom_image_registry):
            full_image_name = f"{self.custom_image_registry}/{custom_image}"
        else:
            full_image_name = custom_image
        
        # Pull image if needed
        if not self._pull_image_with_retry(full_image_name):
            raise RuntimeError(f"Failed to pull custom image: {full_image_name}")
        
        # Create temporary container with custom image
        container = None
        try:
            container = self.client.containers.create(
                full_image_name,
                command="/bin/sh",
                stdin_open=True,
                tty=True,
                mem_limit=self.memory_limit,
                cpu_quota=int(self.cpu_limit * 100000),
                cpu_period=100000,
                network_disabled=True,
                read_only=False,
                tmpfs={'/tmp': 'size=100M'},
                security_opt=["no-new-privileges"],
                cap_drop=["ALL"],
                cap_add=["CHOWN", "SETUID", "SETGID"],
                labels={"pool": "script-executor", "status": "custom", "image": full_image_name}
            )
            container.start()
            logger.info(f"Created custom container {container.short_id} with image {full_image_name}")
            
            return self._execute_in_container(container, script, stdin, start_time)
            
        finally:
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.info(f"Destroyed custom container {container.short_id}")
                except Exception as e:
                    logger.error(f"Failed to destroy custom container: {e}")
    
    def _execute_in_container(self, container, script: str, stdin: Optional[str], start_time: float) -> Dict[str, any]:
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
        
        exec_result = result
        
        execution_time = time.time() - start_time
        
        # Update metrics
        if exec_result.exit_code == 0:
            self.metrics["successful_executions"] += 1
        else:
            self.metrics["failed_executions"] += 1
            
        self.metrics["average_execution_time"] = (
            (self.metrics["average_execution_time"] * (self.metrics["total_executions"] - 1) + execution_time)
            / self.metrics["total_executions"]
        )
        
        return {
            "success": exec_result.exit_code == 0,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exec_result.exit_code,
            "execution_time": execution_time,
            "error": None
        }
    
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
                container.stop(timeout=5)
                container.remove(force=True)
            except:
                pass
        
        for container in self.client.containers.list(all=True, filters={"label": "pool=script-executor"}):
            try:
                container.stop(timeout=5)
                container.remove(force=True)
            except:
                pass


# Flask API Server
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Global container pool
pool = None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "pool_active": pool is not None
    })


@app.route('/execute', methods=['POST'])
def execute_script():
    """Execute a script in a container."""
    try:
        data = request.get_json()
        
        if not data or 'script' not in data:
            return jsonify({
                "success": False,
                "error": "No script provided"
            }), 400
        
        script = data['script']
        stdin = data.get('stdin', None)
        custom_image = data.get('image', None)  # Optional custom image
        
        # Execute script with optional custom image
        result = pool.execute_script(script, stdin, custom_image)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Get pool metrics."""
    return jsonify(pool.get_metrics())


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "success": False,
        "error": "Rate limit exceeded",
        "message": str(e.description)
    }), 429


def create_app(config=None):
    """Create and configure the Flask app."""
    global pool
    
    # Parse custom pools configuration from environment
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
        except Exception as e:
            logger.warning(f"Invalid CUSTOM_POOLS configuration: {e}")
    
    # Default configuration
    default_config = {
        "default_pool_size": int(os.environ.get('POOL_SIZE', 5)),
        "default_image": os.environ.get('BASE_IMAGE', 'alpine:latest'),
        "memory_limit": os.environ.get('MEMORY_LIMIT', '256m'),
        "cpu_limit": float(os.environ.get('CPU_LIMIT', 0.5)),
        "timeout": int(os.environ.get('TIMEOUT', 30)),
        "custom_image_registry": os.environ.get('CUSTOM_IMAGE_REGISTRY', ''),
        "custom_image_pull_timeout": int(os.environ.get('CUSTOM_IMAGE_PULL_TIMEOUT', 300)),
        "custom_image_pull_retries": int(os.environ.get('CUSTOM_IMAGE_PULL_RETRIES', 3)),
        "custom_pools": custom_pools
    }
    
    if config:
        default_config.update(config)
    
    # Initialize multi-pool manager
    pool = MultiPoolManager(**default_config)
    
    return app


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Docker Pool Script Execution Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--pool-size', type=int, default=3, help='Container pool size')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Create app with configuration
    app = create_app({
        "default_pool_size": args.pool_size
    })
    
    try:
        print(f"Starting Docker Pool Server on {args.host}:{args.port}")
        print(f"Pool size: {args.pool_size}")
        print("Press Ctrl+C to stop")
        
        # Run the server
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            threaded=True
        )
    finally:
        if pool:
            pool.shutdown_pools()