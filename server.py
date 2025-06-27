#!/usr/bin/env python3
"""
Refactored Docker Pool Script Execution Server.

A Flask-based server that manages pools of Docker containers for executing
untrusted scripts with optional file attachments.
"""

import argparse
import sys
from src.app import create_app, setup_logging


def main():
    """Main entry point for the server."""
    # Setup logging first
    setup_logging()
    
    # Parse command line arguments
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
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)
    finally:
        # Cleanup is handled by the app teardown handler
        if hasattr(app, 'pool_manager') and app.pool_manager:
            app.pool_manager.shutdown_pools()


if __name__ == '__main__':
    main()