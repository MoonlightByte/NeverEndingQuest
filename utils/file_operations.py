#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Atomic file operations module for safe JSON file handling.
Prevents data corruption by using temporary files and atomic renames.
Cross-platform compatible (Windows/Unix).
"""

# ============================================================================
# FILE_OPERATIONS.PY - DATA PERSISTENCE ABSTRACTION LAYER
# ============================================================================
# 
# ARCHITECTURE ROLE: Data Management Layer - Atomic File Operations
# 
# This module implements our "Data Integrity Above All" principle by providing
# atomic file operations with comprehensive error handling, backup mechanisms,
# and cross-platform compatibility for all game data persistence.
# 
# KEY RESPONSIBILITIES:
# - Atomic file read/write operations with locking mechanisms
# - Automatic backup creation and restoration capabilities
# - UTF-8 encoding with special character sanitization
# - Cross-platform file locking (Windows/Unix compatibility)
# - Graceful error handling with detailed logging
# 
# ATOMIC OPERATION STRATEGY:
# 1. Create temporary file with .tmp extension
# 2. Write data to temporary file
# 3. Atomic rename from .tmp to target filename
# 4. Automatic cleanup on failure
# 5. Backup creation before overwriting existing files
# 
# FILE LOCKING MECHANISM:
# - .lock files prevent concurrent modification
# - Automatic stale lock cleanup after timeout
# - Platform-specific locking strategies
# - Graceful degradation when locking fails
# 
# ARCHITECTURAL INTEGRATION:
# - Used by all modules requiring file persistence
# - Integrates with ModulePathManager for path resolution
# - Supports the module-centric file organization
# - Enables reliable state management across the system
# 
# DESIGN PATTERNS:
# - Template Method: Consistent file operation pipeline
# - Strategy Pattern: Platform-specific locking mechanisms
# - Proxy Pattern: Transparent atomic operations
# 
# This module ensures that all file operations maintain data integrity
# even under failure conditions, supporting our reliability requirements.
# ============================================================================

import json
import os
import shutil
import time
import logging
from typing import Any, Dict, Optional
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class FileLockError(Exception):
    """Raised when unable to acquire file lock"""
    pass

class AtomicFileWriter:
    """Handles atomic file writing with automatic backups and locking"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 0.1):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.lock_files = {}
    
    def acquire_lock(self, filepath: str, timeout: float = 5.0) -> Optional[int]:
        """Acquire exclusive lock on file for writing using lock files"""
        lock_path = f"{filepath}.lock"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file exclusively
                # Using low-level os.open for cross-platform exclusive creation
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                # Write PID to lock file for debugging
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.lock_files[filepath] = lock_path
                logger.debug(f"Acquired lock for {filepath}")
                return 1  # Return non-None to indicate success
            except FileExistsError:
                # Lock file exists, check if it's stale
                if os.path.exists(lock_path):
                    try:
                        # Check if lock file is old (stale)
                        lock_age = time.time() - os.path.getmtime(lock_path)
                        if lock_age > 60:  # Lock older than 60 seconds is considered stale
                            logger.warning(f"Removing stale lock file: {lock_path}")
                            try:
                                os.unlink(lock_path)
                            except:
                                pass
                    except:
                        pass
                # Wait and retry
                time.sleep(self.retry_delay)
            except Exception as e:
                logger.error(f"Error acquiring lock for {filepath}: {e}")
                raise
        
        raise FileLockError(f"Could not acquire lock for {filepath} within {timeout} seconds")
    
    def release_lock(self, filepath: str):
        """Release file lock"""
        if filepath in self.lock_files:
            lock_path = self.lock_files[filepath]
            try:
                if os.path.exists(lock_path):
                    os.unlink(lock_path)
                del self.lock_files[filepath]
                logger.debug(f"Released lock for {filepath}")
            except Exception as e:
                logger.error(f"Error releasing lock for {filepath}: {e}")
    
    def create_backup(self, filepath: str) -> Optional[str]:
        """Create backup of existing file"""
        if not os.path.exists(filepath):
            return None
            
        backup_path = f"{filepath}.bak"
        try:
            shutil.copy2(filepath, backup_path)
            logger.debug(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error creating backup for {filepath}: {e}")
            raise
    
    def write_json(self, filepath: str, data: Dict[str, Any], 
                   create_backup: bool = True, acquire_lock: bool = True) -> bool:
        """
        Atomically write JSON data to file with optional backup and locking.
        
        Args:
            filepath: Path to the JSON file
            data: Dictionary to write as JSON
            create_backup: Whether to create a backup before writing
            acquire_lock: Whether to use file locking
            
        Returns:
            True if successful, False otherwise
        """
        filepath = str(filepath)  # Handle Path objects
        temp_path = f"{filepath}.tmp"
        backup_path = None
        lock_acquired = False
        
        try:
            # Acquire lock if requested
            if acquire_lock:
                print(f"DEBUG: [FILE_OPS] Attempting to acquire lock for {filepath}")
                self.acquire_lock(filepath)
                lock_acquired = True
                print(f"DEBUG: [FILE_OPS] Lock acquired successfully")
            
            # Create backup if requested and file exists
            if create_backup and os.path.exists(filepath):
                backup_path = self.create_backup(filepath)
            
            # Ensure directory exists
            dir_path = os.path.dirname(filepath)
            if dir_path:  # Only create directory if dirname is not empty
                os.makedirs(dir_path, exist_ok=True)
            
            # Write to temporary file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write('\n')  # Add newline at end of file
                f.flush()
                # Force write to disk
                try:
                    os.fsync(f.fileno())
                except:
                    # fsync might not work on all systems, that's OK
                    pass
            
            # Replace the target in one filesystem operation. In particular,
            # never unlink first on Windows: a crash in that gap loses the
            # only committed copy of the JSON document.
            os.replace(temp_path, filepath)
            # Suppress success messages - only log errors
            # logger.info(f"Successfully wrote {filepath}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing {filepath}: {e}")
            
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            
            # Restore backup if write failed
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, filepath)
                    logger.info(f"Restored backup for {filepath}")
                except Exception as restore_error:
                    logger.error(f"Failed to restore backup: {restore_error}")
            
            return False
            
        finally:
            # Always release lock
            if lock_acquired:
                self.release_lock(filepath)
    
    def read_json(self, filepath: str, acquire_lock: bool = False) -> Optional[Dict[str, Any]]:
        """
        Safely read JSON file with optional locking.
        
        Args:
            filepath: Path to the JSON file
            acquire_lock: Whether to use file locking for read
            
        Returns:
            Dictionary containing JSON data, or None if error
        """
        filepath = str(filepath)
        lock_acquired = False
        
        try:
            # Acquire lock if requested (usually not needed for reads)
            if acquire_lock:
                self.acquire_lock(filepath)
                lock_acquired = True
            
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Suppress success messages - only log errors
                # logger.debug(f"Successfully read {filepath}")
                return data
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return None
        finally:
            if lock_acquired:
                self.release_lock(filepath)
    
    def cleanup_lock_files(self):
        """Clean up any remaining lock files (call on exit)"""
        for filepath in list(self.lock_files.keys()):
            self.release_lock(filepath)

# Global instance for convenience
atomic_writer = AtomicFileWriter()

# Convenience functions
def safe_write_json(filepath: str, data: Dict[str, Any], 
                   create_backup: bool = True, acquire_lock: bool = True) -> bool:
    """Atomically write JSON data to file"""
    return atomic_writer.write_json(filepath, data, create_backup, acquire_lock)

def safe_read_json(filepath: str, acquire_lock: bool = False) -> Optional[Dict[str, Any]]:
    """Safely read JSON file"""
    return atomic_writer.read_json(filepath, acquire_lock)

def cleanup_locks():
    """Clean up any remaining lock files"""
    atomic_writer.cleanup_lock_files()

# Example usage and migration guide
if __name__ == "__main__":
    # Test atomic write
    test_data = {"test": "data", "number": 42}
    
    print("Testing atomic file operations...")
    
    # Write test
    if safe_write_json("test_atomic.json", test_data):
        print("[OK] Write successful")
    else:
        print("[ERROR] Write failed")
    
    # Read test
    read_data = safe_read_json("test_atomic.json")
    if read_data == test_data:
        print("[OK] Read successful")
    else:
        print("[ERROR] Read failed")
    
    # Cleanup test file
    if os.path.exists("test_atomic.json"):
        os.unlink("test_atomic.json")
    if os.path.exists("test_atomic.json.bak"):
        os.unlink("test_atomic.json.bak")
    
    print("\nMigration guide:")
    print("Replace:")
    print('  with open("file.json", "w") as f:')
    print('      json.dump(data, f, indent=2)')
    print("\nWith:")
    print('  safe_write_json("file.json", data)')
    print("\nOr import and use:")
    print('  from utils.file_operations import safe_write_json, safe_read_json')