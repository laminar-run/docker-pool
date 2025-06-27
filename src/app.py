"""Application factory and configuration for the Docker Pool Server."""

import logging
from flask import Flask

from .config import DEFAULT_CONFIG, parse_custom_pools
from .pool_manager import MultiPoolManager
from .file_manager import FileSessionManager
from .api import create_api_routes

logger = logging.getLogger(__name__)


def create_app(config=None):
    """Create and configure the Flask app."""
    # Create Flask app
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False
    
    # Parse custom pools configuration from environment
    custom_pools = parse_custom_pools()
    if custom_pools:
        logger.info(f"Parsed custom pools configuration: {custom_pools}")
    
    # Merge configurations
    app_config = DEFAULT_CONFIG.copy()
    app_config["custom_pools"] = custom_pools
    
    if config:
        app_config.update(config)
    
    # Initialize multi-pool manager
    pool_manager = MultiPoolManager(**app_config)
    
    # Initialize file session manager
    file_manager = FileSessionManager()
    
    # Store managers in app context for access in routes
    app.pool_manager = pool_manager
    app.file_manager = file_manager
    
    # Create API routes
    create_api_routes(app, pool_manager, file_manager)
    
    # Note: Pool cleanup is handled in the main server shutdown, not per-request
    # @app.teardown_appcontext would shut down pools after every request
    
    return app


def setup_logging():
    """Configure logging for the application."""
    import os
    
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )