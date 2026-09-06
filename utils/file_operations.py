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
# - Installation-owned runtime locks prevent concurrent modification
# - OS ownership releases automatically when a process exits
# - Platform-specific locking strategies
# - Cancellable ownership polling without abandoning pending writes
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
import hashlib
import os
import shutil
import time
import threading
import logging
from typing import Any, Dict, Optional
from pathlib import Path
from contextlib import nullcontext
from utils.capture.live_provider_call import LiveProviderSuperseded
from utils.module_refresh_lock import RUNTIME_LOCKS_DIR
from utils.path_transaction_lock import path_transaction_lock
from utils.transient_filesystem import is_transient_filesystem_error

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
    
    def acquire_lock(self, filepath: str, timeout=None, *, commit_guard=None) -> Optional[int]:
        """Wait for OS ownership; timeout is retained only for API compatibility."""
        canonical = os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(filepath))))
        runtime_lock_target = os.path.join(
            RUNTIME_LOCKS_DIR, "atomic", hashlib.sha256(os.fsencode(canonical)).hexdigest()
        )
        key = (os.getpid(), threading.get_ident(), canonical)
        while True:
            if commit_guard is not None:
                with commit_guard():
                    pass
            ownership = path_transaction_lock(
                runtime_lock_target, suffix=".lock",
                timeout_seconds=self.retry_delay, poll_seconds=self.retry_delay,
            )
            try:
                acquired = ownership.__enter__()
            except OSError as exc:
                if not is_transient_filesystem_error(exc):
                    raise
                time.sleep(self.retry_delay)
                continue
            if acquired is None:
                ownership.__exit__(None, None, None)
                continue
            try:
                if commit_guard is not None:
                    with commit_guard():
                        pass
                self.lock_files.setdefault(key, []).append(ownership)
            except BaseException:
                ownership.__exit__(None, None, None)
                raise
            logger.debug("Acquired lock for %s", canonical)
            return 1

    def release_lock(self, filepath: str):
        """Release only this thread's ownership, retaining the advisory inode."""
        canonical = os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(filepath))))
        key = (os.getpid(), threading.get_ident(), canonical)
        stack = self.lock_files.get(key)
        if not stack:
            return
        ownership = stack.pop()
        if not stack:
            del self.lock_files[key]
        ownership.__exit__(None, None, None)
        logger.debug("Released lock for %s", canonical)
    
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
                   create_backup: bool = True, acquire_lock: bool = True,
                   *, commit_guard=None) -> bool:
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
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            # Acquire lock if requested
            if acquire_lock:
                print(f"DEBUG: [FILE_OPS] Attempting to acquire lock for {filepath}")
                self.acquire_lock(filepath, commit_guard=commit_guard)
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
            # Windows can transiently refuse the rename (WinError 5/32) while
            # an antivirus scan, indexer, or reader briefly holds the
            # destination. One such blip must not fail the write - a live
            # acceptance run lost an entire combat to a single WinError 5
            # here. Retry sharing contention patiently; nonretryable errors
            # still follow the existing error path below.
            _replace_attempt = 0
            while True:
                try:
                    with commit_guard() if commit_guard is not None else nullcontext():
                        os.replace(temp_path, filepath)
                    break
                except (PermissionError, OSError) as replace_error:
                    winerror = getattr(replace_error, "winerror", None)
                    if winerror not in (5, 32):
                        raise
                    _replace_attempt += 1
                    if _replace_attempt % 20 == 0:
                        logger.warning(
                            f"Transient Windows rename contention on "
                            f"{filepath} (WinError {winerror}), attempt "
                            f"{_replace_attempt}; still retrying"
                        )
                    time.sleep(0.1)
            # Suppress success messages - only log errors
            # logger.info(f"Successfully wrote {filepath}")
            
            return True
            
        except LiveProviderSuperseded:
            raise
        except Exception as e:
            logger.error(f"Error writing {filepath}: {e}")
            
            # Atomic replace leaves the original authoritative on every
            # pre-commit failure. Re-copying the backup over that intact file
            # would introduce a second, non-atomic corruption window.
            
            return False
            
        finally:
            if os.path.exists(temp_path) and (lock_acquired or not acquire_lock):
                try:
                    os.unlink(temp_path)
                except OSError as exc:
                    logger.warning("Could not clean temporary file %s: %s", temp_path, exc)
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
        """Drain only contexts owned by the calling process and thread."""
        owner = (os.getpid(), threading.get_ident())
        for key in list(self.lock_files):
            if key[:2] == owner:
                while key in self.lock_files:
                    self.release_lock(key[2])

# Global instance for convenience
atomic_writer = AtomicFileWriter()

# Convenience functions
def safe_write_json(filepath: str, data: Dict[str, Any], 
                   create_backup: bool = True, acquire_lock: bool = True,
                   *, commit_guard=None) -> bool:
    """Atomically write JSON data to file"""
    return atomic_writer.write_json(filepath, data, create_backup, acquire_lock,
                                    commit_guard=commit_guard)

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
