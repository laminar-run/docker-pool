"""File session management for script execution with file attachments."""

import os
import shutil
import tempfile
import threading
import time
import uuid
import zipfile
from typing import Dict, Optional, List, Tuple
import logging
from werkzeug.utils import secure_filename

from .config import (
    MAX_FILE_SIZE, MAX_TOTAL_SIZE, ALLOWED_EXTENSIONS,
    ZIP_SUPPORT_ENABLED, ZIP_MAX_EXTRACTED_SIZE, ZIP_MAX_FILES,
    ZIP_MAX_COMPRESSION_RATIO, ZIP_EXTRACTION_TIMEOUT,
    ZIP_MAX_NESTED_DEPTH, ZIP_ALLOWED_EXTENSIONS
)

logger = logging.getLogger(__name__)


class FileSessionManager:
    """Manages file sessions for script execution with file attachments."""
    
    def __init__(self, base_temp_dir: str = None):
        self.base_temp_dir = base_temp_dir or tempfile.gettempdir()
        self.sessions = {}  # session_id -> session_info
        self.session_lock = threading.Lock()
        
        # Create base directory for file sessions
        self.sessions_dir = os.path.join(self.base_temp_dir, 'docker_pool_sessions')
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        logger.info(f"FileSessionManager initialized with base dir: {self.sessions_dir}")
    
    def create_session(self) -> str:
        """Create a new file session and return session ID."""
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(self.sessions_dir, session_id)
        
        with self.session_lock:
            os.makedirs(session_dir, exist_ok=True)
            self.sessions[session_id] = {
                'session_dir': session_dir,
                'files': {},
                'created_at': time.time(),
                'total_size': 0
            }
        
        logger.info(f"Created file session: {session_id}")
        return session_id
    
    def add_file(self, session_id: str, filename: str, file_content: bytes) -> bool:
        """Add a file to the session. Returns True if successful."""
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return False
        
        # Validate file size
        if len(file_content) > MAX_FILE_SIZE:
            logger.error(f"File {filename} exceeds maximum size limit")
            return False
        
        # Validate total session size
        session_info = self.sessions[session_id]
        if session_info['total_size'] + len(file_content) > MAX_TOTAL_SIZE:
            logger.error(f"Adding file {filename} would exceed total size limit")
            return False
        
        # Check if it's a ZIP file and ZIP support is enabled
        if ZIP_SUPPORT_ENABLED and filename.lower().endswith('.zip'):
            return self._handle_zip_file(session_id, filename, file_content)
        
        # Validate file extension
        if not self._is_allowed_file(filename):
            logger.error(f"File type not allowed: {filename}")
            return False
        
        # Secure the filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            logger.error(f"Invalid filename: {filename}")
            return False
        
        # Save file to session directory
        file_path = os.path.join(session_info['session_dir'], safe_filename)
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Update session info
            with self.session_lock:
                session_info['files'][safe_filename] = {
                    'original_name': filename,
                    'path': file_path,
                    'size': len(file_content),
                    'type': 'regular'
                }
                session_info['total_size'] += len(file_content)
            
            logger.info(f"Added file {safe_filename} to session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save file {filename}: {e}")
            return False
    
    def copy_files_to_container_workspace(self, session_id: str, workspace_dir: str) -> bool:
        """Copy session files to container workspace directory."""
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            return False
        
        session_info = self.sessions[session_id]
        files_dir = os.path.join(workspace_dir, 'files')
        
        try:
            os.makedirs(files_dir, exist_ok=True)
            
            for filename, file_info in session_info['files'].items():
                file_type = file_info.get('type', 'regular')
                
                if file_type == 'zip_archive':
                    # Handle extracted ZIP files
                    extracted_files = file_info.get('extracted_files', [])
                    for extracted_file in extracted_files:
                        src_path = extracted_file['path']
                        # Preserve directory structure from ZIP
                        rel_path = extracted_file['filename']
                        dst_path = os.path.join(files_dir, rel_path)
                        
                        # Create directory structure
                        dst_dir = os.path.dirname(dst_path)
                        os.makedirs(dst_dir, exist_ok=True)
                        
                        shutil.copy2(src_path, dst_path)
                        logger.debug(f"Copied extracted file {rel_path} to container workspace")
                else:
                    # Handle regular files
                    src_path = file_info['path']
                    dst_path = os.path.join(files_dir, filename)
                    shutil.copy2(src_path, dst_path)
                    logger.debug(f"Copied {filename} to container workspace")
            
            logger.info(f"Copied files from {len(session_info['files'])} file entries to workspace: {workspace_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy files to workspace: {e}")
            return False
    
    def cleanup_session(self, session_id: str):
        """Clean up a file session and remove all associated files."""
        if session_id not in self.sessions:
            return
        
        session_info = self.sessions[session_id]
        session_dir = session_info['session_dir']
        
        try:
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                logger.info(f"Cleaned up session directory: {session_dir}")
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")
        
        with self.session_lock:
            del self.sessions[session_id]
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get information about a session."""
        return self.sessions.get(session_id)
    
    def _handle_zip_file(self, session_id: str, filename: str, file_content: bytes) -> bool:
        """Handle ZIP file with comprehensive security checks."""
        try:
            # Create temporary file for ZIP processing
            temp_zip_path = os.path.join(self.sessions[session_id]['session_dir'], f"temp_{filename}")
            with open(temp_zip_path, 'wb') as f:
                f.write(file_content)
            
            # Perform security checks
            if not self._is_zip_bomb(temp_zip_path):
                os.unlink(temp_zip_path)
                logger.error(f"ZIP bomb detected in {filename}")
                return False
            
            # Extract ZIP safely
            extracted_files = self._extract_zip_safely(session_id, temp_zip_path, filename)
            
            # Clean up temporary ZIP file
            os.unlink(temp_zip_path)
            
            if extracted_files is None:
                logger.error(f"Failed to extract ZIP file {filename}")
                return False
            
            # Validate extracted files
            if not self._validate_extracted_files(session_id, extracted_files):
                logger.error(f"Extracted files from {filename} failed validation")
                return False
            
            # Update session info with ZIP extraction details
            session_info = self.sessions[session_id]
            with self.session_lock:
                session_info['files'][f"{filename}_extracted"] = {
                    'original_name': filename,
                    'type': 'zip_archive',
                    'extracted_files': extracted_files,
                    'size': len(file_content)
                }
            
            logger.info(f"Successfully extracted ZIP file {filename} with {len(extracted_files)} files")
            return True
            
        except Exception as e:
            logger.error(f"Error handling ZIP file {filename}: {e}")
            return False
    
    def _is_zip_bomb(self, zip_path: str) -> bool:
        """Check if ZIP file is a zip bomb by analyzing compression ratios."""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                total_compressed = 0
                total_uncompressed = 0
                file_count = 0
                
                for info in zf.infolist():
                    file_count += 1
                    
                    # Check file count limit
                    if file_count > ZIP_MAX_FILES:
                        logger.warning(f"ZIP contains too many files: {file_count} > {ZIP_MAX_FILES}")
                        return False
                    
                    total_compressed += info.compress_size
                    total_uncompressed += info.file_size
                    
                    # Check individual file size
                    if info.file_size > MAX_FILE_SIZE:
                        logger.warning(f"ZIP contains file too large: {info.filename} ({info.file_size} bytes)")
                        return False
                    
                    # Check for path traversal
                    if not self._validate_zip_path(info.filename):
                        logger.warning(f"ZIP contains unsafe path: {info.filename}")
                        return False
                
                # Check total extracted size
                if total_uncompressed > ZIP_MAX_EXTRACTED_SIZE:
                    logger.warning(f"ZIP extracted size too large: {total_uncompressed} > {ZIP_MAX_EXTRACTED_SIZE}")
                    return False
                
                # Check compression ratio
                if total_compressed > 0:
                    compression_ratio = total_uncompressed / total_compressed
                    if compression_ratio > ZIP_MAX_COMPRESSION_RATIO:
                        logger.warning(f"ZIP compression ratio too high: {compression_ratio} > {ZIP_MAX_COMPRESSION_RATIO}")
                        return False
                
                return True
                
        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file: {zip_path}")
            return False
        except Exception as e:
            logger.error(f"Error analyzing ZIP file {zip_path}: {e}")
            return False
    
    def _validate_zip_path(self, path: str) -> bool:
        """Validate ZIP file path to prevent directory traversal."""
        # Normalize path
        normalized = os.path.normpath(path)
        
        # Check for absolute paths
        if os.path.isabs(normalized):
            return False
        
        # Check for parent directory references
        if '..' in normalized.split(os.sep):
            return False
        
        # Check for hidden files/directories (optional security measure)
        if any(part.startswith('.') for part in normalized.split(os.sep)):
            logger.warning(f"ZIP contains hidden file/directory: {path}")
        
        return True
    
    def _extract_zip_safely(self, session_id: str, zip_path: str, original_filename: str) -> Optional[List[Dict]]:
        """Extract ZIP file safely with timeout and resource limits."""
        session_info = self.sessions[session_id]
        extract_dir = os.path.join(session_info['session_dir'], 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        
        extracted_files = []
        timeout_occurred = threading.Event()
        timer = None
        
        def timeout_handler():
            timeout_occurred.set()
        
        try:
            # Set extraction timeout using threading.Timer (thread-safe)
            timer = threading.Timer(ZIP_EXTRACTION_TIMEOUT, timeout_handler)
            timer.start()
            
            with zipfile.ZipFile(zip_path, 'r') as zf:
                total_extracted_size = 0
                
                for info in zf.infolist():
                    # Check for timeout
                    if timeout_occurred.is_set():
                        raise TimeoutError("ZIP extraction timeout")
                    
                    # Skip directories
                    if info.is_dir():
                        continue
                    
                    # Validate path again during extraction
                    if not self._validate_zip_path(info.filename):
                        continue
                    
                    # Create safe extraction path
                    safe_path = os.path.join(extract_dir, info.filename)
                    safe_dir = os.path.dirname(safe_path)
                    
                    # Ensure extraction path is within extract_dir
                    if not safe_path.startswith(extract_dir):
                        logger.warning(f"Skipping file with unsafe path: {info.filename}")
                        continue
                    
                    # Create directory structure
                    os.makedirs(safe_dir, exist_ok=True)
                    
                    # Extract file
                    with zf.open(info) as source, open(safe_path, 'wb') as target:
                        extracted_size = 0
                        while True:
                            # Check for timeout during extraction
                            if timeout_occurred.is_set():
                                raise TimeoutError("ZIP extraction timeout")
                            
                            chunk = source.read(8192)
                            if not chunk:
                                break
                            
                            extracted_size += len(chunk)
                            total_extracted_size += len(chunk)
                            
                            # Check size limits during extraction
                            if extracted_size > MAX_FILE_SIZE:
                                raise ValueError(f"Extracted file {info.filename} exceeds size limit")
                            
                            if total_extracted_size > ZIP_MAX_EXTRACTED_SIZE:
                                raise ValueError("Total extracted size exceeds limit")
                            
                            target.write(chunk)
                    
                    # Update session total size
                    with self.session_lock:
                        session_info['total_size'] += extracted_size
                    
                    extracted_files.append({
                        'filename': info.filename,
                        'path': safe_path,
                        'size': extracted_size,
                        'from_zip': original_filename
                    })
            
            # Cancel timeout if extraction completed successfully
            if timer:
                timer.cancel()
            return extracted_files
            
        except TimeoutError:
            logger.error(f"ZIP extraction timeout for {original_filename}")
            return None
        except Exception as e:
            logger.error(f"Error extracting ZIP {original_filename}: {e}")
            return None
        finally:
            # Ensure timeout timer is cancelled
            if timer:
                timer.cancel()
    
    def _validate_extracted_files(self, session_id: str, extracted_files: List[Dict]) -> bool:
        """Validate all extracted files against security policies."""
        nested_archives = 0
        
        for file_info in extracted_files:
            filename = file_info['filename']
            file_path = file_info['path']
            
            # Check file extension
            if not self._is_allowed_extracted_file(filename):
                logger.warning(f"Extracted file has disallowed extension: {filename}")
                # Remove the file
                try:
                    os.unlink(file_path)
                except:
                    pass
                return False
            
            # Check for nested archives
            if self._is_archive_file(filename):
                nested_archives += 1
                if nested_archives > ZIP_MAX_NESTED_DEPTH:
                    logger.warning(f"Too many nested archives detected: {nested_archives}")
                    return False
            
            # Additional content validation could be added here
            # (e.g., scanning for malicious patterns)
        
        return True
    
    def _is_allowed_extracted_file(self, filename: str) -> bool:
        """Check if extracted file extension is allowed."""
        if '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in ZIP_ALLOWED_EXTENSIONS
    
    def _is_archive_file(self, filename: str) -> bool:
        """Check if file is an archive type."""
        if '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        archive_extensions = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'}
        return extension in archive_extensions
    
    def _is_allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed."""
        if '.' not in filename:
            return False
        
        extension = filename.rsplit('.', 1)[1].lower()
        return extension in ALLOWED_EXTENSIONS
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up sessions older than max_age_hours."""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        sessions_to_cleanup = []
        with self.session_lock:
            for session_id, session_info in self.sessions.items():
                if current_time - session_info['created_at'] > max_age_seconds:
                    sessions_to_cleanup.append(session_id)
        
        for session_id in sessions_to_cleanup:
            logger.info(f"Cleaning up old session: {session_id}")
            self.cleanup_session(session_id)