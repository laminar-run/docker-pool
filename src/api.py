"""Flask API endpoints for the Docker Pool Server."""

import time
import logging
from flask import Flask, request, jsonify

from .config import MAX_FILE_SIZE, MAX_TOTAL_SIZE

logger = logging.getLogger(__name__)


def create_api_routes(app: Flask, pool_manager, file_manager):
    """Create and register API routes with the Flask app."""
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "timestamp": time.time(),
            "pool_active": pool_manager is not None
        })

    @app.route('/execute', methods=['POST'])
    def execute_script():
        """Execute a script in a container with optional file attachments."""
        session_id = None
        try:
            # Check content type to determine how to parse the request
            content_type = request.content_type or ''
            
            if 'multipart/form-data' in content_type:
                # Handle multipart form data (with file attachments)
                script = request.form.get('script')
                stdin = request.form.get('stdin', None)
                custom_image = request.form.get('image', None)
                
                if not script:
                    return jsonify({
                        "success": False,
                        "error": "No script provided"
                    }), 400
                
                # Handle file attachments
                files = request.files.getlist('files')
                if files and any(f.filename for f in files):
                    # Create a file session
                    session_id = file_manager.create_session()
                    
                    # Process each file
                    total_size = 0
                    for file in files:
                        if file.filename:
                            # Read file content
                            file_content = file.read()
                            
                            # Validate individual file size
                            if len(file_content) > MAX_FILE_SIZE:
                                file_manager.cleanup_session(session_id)
                                return jsonify({
                                    "success": False,
                                    "error": f"File {file.filename} exceeds maximum size limit of {MAX_FILE_SIZE // (1024*1024)}MB"
                                }), 400
                            
                            total_size += len(file_content)
                            
                            # Validate total size
                            if total_size > MAX_TOTAL_SIZE:
                                file_manager.cleanup_session(session_id)
                                return jsonify({
                                    "success": False,
                                    "error": f"Total file size exceeds maximum limit of {MAX_TOTAL_SIZE // (1024*1024)}MB"
                                }), 400
                            
                            # Add file to session
                            if not file_manager.add_file(session_id, file.filename, file_content):
                                file_manager.cleanup_session(session_id)
                                return jsonify({
                                    "success": False,
                                    "error": f"Failed to process file: {file.filename}"
                                }), 400
                    
                    logger.info(f"Created file session {session_id} with {len([f for f in files if f.filename])} files")
            
            elif 'application/json' in content_type or not content_type:
                # Handle JSON data (traditional API)
                data = request.get_json()
                
                if not data or 'script' not in data:
                    return jsonify({
                        "success": False,
                        "error": "No script provided"
                    }), 400
                
                script = data['script']
                stdin = data.get('stdin', None)
                custom_image = data.get('image', None)
            
            else:
                return jsonify({
                    "success": False,
                    "error": f"Unsupported content type: {content_type}"
                }), 400
            
            # Execute script with optional custom image and file session
            result = pool_manager.execute_script(script, stdin, custom_image, session_id, file_manager)
            
            # Add file information to result if files were attached
            if session_id:
                session_info = file_manager.get_session_info(session_id)
                if session_info:
                    files_info = []
                    zip_extractions = []
                    
                    for filename, file_info in session_info['files'].items():
                        file_type = file_info.get('type', 'regular')
                        
                        if file_type == 'zip_archive':
                            extracted_files = file_info.get('extracted_files', [])
                            zip_extractions.append({
                                'zip_file': file_info['original_name'],
                                'extracted_count': len(extracted_files),
                                'extracted_files': [f['filename'] for f in extracted_files]
                            })
                            files_info.append(f"{file_info['original_name']} (ZIP - {len(extracted_files)} files extracted)")
                        else:
                            files_info.append(filename)
                    
                    result['files_attached'] = files_info
                    result['total_file_size'] = session_info['total_size']
                    
                    if zip_extractions:
                        result['zip_extractions'] = zip_extractions
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"API error: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
        
        finally:
            # Clean up file session after execution
            if session_id:
                file_manager.cleanup_session(session_id)

    @app.route('/metrics', methods=['GET'])
    def get_metrics():
        """Get pool metrics."""
        return jsonify(pool_manager.get_metrics())

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({
            "success": False,
            "error": "Rate limit exceeded",
            "message": str(e.description)
        }), 429

    return app