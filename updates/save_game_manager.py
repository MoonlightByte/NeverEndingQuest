#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Save Game Manager Module for NeverEndingQuest

Handles save and restore functionality for game state preservation.
"""

# ============================================================================
# SAVE_GAME_MANAGER.PY - GAME STATE PERSISTENCE SYSTEM
# ============================================================================
# 
# ARCHITECTURE ROLE: Data Management Layer - Game State Persistence
# 
# This module implements comprehensive save and restore functionality for the
# 5th edition Dungeon Master system, preserving complete game state while maintaining
# module-centric architecture and conversation timeline integrity.
# 
# KEY RESPONSIBILITIES:
# - Atomic save game creation with file categorization
# - Module-aware save directory management
# - Complete game state restoration with validation
# - Save metadata generation and management
# - File integrity checking and backup creation
# - Cross-module save game compatibility
# 
# SAVE SYSTEM DESIGN:
# - Module-specific save directories in modules/[module]/saved_games/
# - Timestamped save folders with descriptive metadata
# - Essential vs. optional file categorization
# - Atomic save operations using existing file_operations.py
# - ZIP compression for storage efficiency (optional)
# 
# RESTORE SYSTEM DESIGN:
# - Save game discovery and metadata parsing
# - Atomic restoration with current state backup
# - File integrity validation before restoration
# - Module compatibility checking
# - Graceful error handling and rollback
# 
# ARCHITECTURAL INTEGRATION:
# - Uses ModulePathManager for consistent file access
# - Leverages file_operations.py for atomic operations
# - Integrates with existing backup and validation systems
# - Supports module-centric directory structure
# - Maintains conversation timeline preservation
# 
# DESIGN PATTERNS:
# - Strategy Pattern: Different save modes (minimal vs. full)
# - Template Method: Consistent save/restore pipeline
# - Builder Pattern: Save metadata construction
# - Observer Pattern: Save progress notifications
# 
# This module ensures reliable game state persistence while maintaining
# the module-centric architecture and data integrity principles.
# ============================================================================

import json
import os
import shutil
import tempfile
import zipfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
# Import our existing utilities
from utils.file_operations import safe_write_json, safe_read_json
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# TABLETOP MODE: Memory foundation integration for Many Worlds support
try:
    from core.memory.memory_db import DEFAULT_MEMORY_DB_PATH
    from core.memory.memory_portability import (
        export_memory_db_package,
        import_memory_db_package,
        validate_memory_package,
    )
    from core.memory.session_diary import confirm_diary_for_save
    MEMORY_PARITY_ENABLED = True
    SESSION_DIARY_ENABLED = True
except ImportError:
    MEMORY_PARITY_ENABLED = False
    SESSION_DIARY_ENABLED = False
    DEFAULT_MEMORY_DB_PATH = "data/memory.db"

# Restore context file for fork-on-first-save-after-restore behavior
RESTORE_CONTEXT_FILE = "modules/conversation_history/restore_context.json"

# TABLETOP MODE: Root archive export directory for USB-portable campaign archives
# Archives are exported here for easy external backup/transport
ARCHIVE_EXPORTS_DIR = "archive_exports"

# Set script name for logging
set_script_name(__name__)

class SaveGameManager:
    """Manages save and restore operations for the Dungeon Master system"""
    
    def __init__(self):
        self.current_module = None
        self.path_manager = None
        self._current_worldline: Optional[str] = None
        self._initialize_module_context()
    
    def _initialize_module_context(self):
        """Initialize the current module context from party tracker"""
        try:
            party_tracker = safe_json_load("party_tracker.json")
            if party_tracker:
                self.current_module = party_tracker.get("module", "").replace(" ", "_")
                self.path_manager = ModulePathManager(self.current_module)
            else:
                self.path_manager = ModulePathManager()
        except Exception as e:
            warning(f"INITIALIZATION: Could not initialize module context", category="save_game")
            self.path_manager = ModulePathManager()
    
    def _get_archive_exports_directory(self) -> str:
        """Get the root archive exports directory path.
        
        TABLETOP MODE: Returns the path to the root archive_exports folder
        for USB-portable campaign archive storage.
        
        Returns:
            Absolute path to archive_exports/ directory
        """
        # Resolve from repository root (where the script is run from)
        repo_root = os.path.abspath(".")
        archive_dir = os.path.join(repo_root, ARCHIVE_EXPORTS_DIR)
        
        # Ensure directory exists (idempotent)
        try:
            os.makedirs(archive_dir, exist_ok=True)
        except Exception as e:
            warning(f"ARCHIVE_EXPORT: Could not create archive_exports directory: {e}", category="save_game")
        
        return archive_dir

    def _get_world_conditions_for_diary(self) -> Dict[str, Any]:
        """Get current world conditions for diary checkpoint generation."""
        try:
            party_tracker = safe_json_load("party_tracker.json")
            if isinstance(party_tracker, dict):
                world_conditions = party_tracker.get("worldConditions", {})
                if isinstance(world_conditions, dict):
                    return world_conditions
        except Exception as world_error:
            warning(
                f"SESSION_DIARY: Could not load world conditions for save checkpoint: {world_error}",
                category="save_game",
            )
        return {}

    def _confirm_session_diary_checkpoint(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Best-effort confirmed diary checkpoint for save creation."""
        save_id = str(metadata.get("save_id", "")).strip()
        if not SESSION_DIARY_ENABLED:
            return {
                "status": "disabled",
                "message": "Session diary unavailable",
            }

        if not save_id:
            return {
                "status": "error",
                "message": "Missing save_id for diary checkpoint",
            }

        try:
            result = confirm_diary_for_save(
                DEFAULT_MEMORY_DB_PATH,
                save_id,
                self._get_world_conditions_for_diary(),
            )
            if result.get("status") == "success":
                info(
                    f"SESSION_DIARY: Confirmed diary checkpoint action={result.get('action')} save_id={save_id}",
                    category="save_game",
                )
            else:
                warning(
                    f"SESSION_DIARY: Diary checkpoint degraded for save_id={save_id} status={result.get('status')}",
                    category="save_game",
                )
            return result
        except Exception as diary_error:
            error(
                f"SESSION_DIARY: Diary checkpoint failed for save_id={save_id}: {diary_error}",
                exception=diary_error,
                category="save_game",
            )
            return {
                "status": "error",
                "message": str(diary_error),
            }
    
    def get_essential_files(self) -> List[str]:
        """Get list of essential files that must be saved for game state"""
        essential_files = [
            # Global state files
            "party_tracker.json",
            "current_location.json", 
            "journal.json",
            "player_storage.json",
            
            # Critical game data files
            "data/spell_repository.json",
            "training_data.json",
            "modules/conversation_history/combat_conversation_history.json",
            
            # Conversation and chat history (critical for game continuity)
            "modules/conversation_history/conversation_history.json",
            "modules/conversation_history/chat_history.json",
            
            # Character data
            "characters/",
            
            # Character portraits (added for portrait system)
            "web/static/portraits/",
            
            # Active encounters - we need to use glob to find these
            # Will be handled separately
        ]
        
        # Module-specific files if we have a current module
        if self.current_module and self.path_manager:
            module_base = f"modules/{self.current_module}"
            essential_files.extend([
                f"{module_base}/module_plot.json",
                f"{module_base}/module_context.json", 
                f"{module_base}/areas/",
                f"{module_base}/characters/",
                f"{module_base}/monsters/",
                f"{module_base}/encounters/",
                f"{module_base}/portraits/",  # Module-specific portraits
                # CRITICAL: Include BU files for reset functionality
                f"{module_base}/areas/*_BU.json",
                f"{module_base}/*_BU.json",
            ])
        
        # Global module files
        essential_files.extend([
            "modules/campaign.json",
            "modules/world_registry.json",
            "modules/effects_tracker.json",
            "modules/default/effects_tracker.json",
        ])
        
        # Campaign continuity files (CRITICAL for module transitions)
        essential_files.extend([
            "modules/campaign_archives/",
            "modules/campaign_summaries/",
        ])
        
        # Add active encounter files using glob
        import glob
        encounter_files = glob.glob("modules/encounters/encounter_*.json")
        essential_files.extend(encounter_files)
        
        return essential_files
    
    def get_optional_files(self) -> List[str]:
        """Get list of optional files for full save mode"""
        return [
            # Additional conversation history
            "modules/conversation_history/second_model_history.json", 
            "modules/conversation_history/third_model_history.json",
            
            # Combat logs
            "combat_logs/",
            
            # Note: Campaign archives and summaries moved to essential files
            # as they're critical for module transition continuity
        ]
    
    def get_excluded_patterns(self) -> List[str]:
        """Get list of file patterns to exclude from saves"""
        return [
            # Debug and log files
            "*.log",
            "debug_*",
            "game_debug.log",
            "game_errors.log",
            "http_server.log",
            "web_server.log",
            
            # Backup directories
            "campaign_backup_*",
            "backup_pre_integration_*", 
            "*_backup_*",
            "modules/backups/",
            
            # CRITICAL: Exclude save directories to prevent recursive nesting
            "saved_games/",
            "*/saved_games/*",
            "save_20*",  # Exclude any save folders
            
            # Temporary files
            "*.tmp",
            "*.bak",
            "*.backup_*",
            # NOTE: *_BU.json files are now INCLUDED in saves as they are critical
            # for the reset_campaign.py functionality
            
            # Python source and schemas
            "*.py",
            "*_schema.json",
            
            # Development files
            "test_*",
            "testing/",
            "isolated_testing/",
            "debug_log_backups/",
            
            # Screenshots and documentation
            "*.png",
            "*.md",
            "*.txt",
            "*.html",
            "*.css",
            
            # Static assets
            "static/",
            "templates/",
            "icons/",
        ]
    
    def should_include_file(self, filepath: str, save_mode: str = "essential") -> bool:
        """Determine if a file should be included in the save"""
        # Convert to forward slashes for consistent pattern matching
        filepath = filepath.replace("\\", "/")
        
        # Special case: Always include portrait images
        if "/portraits/" in filepath and filepath.endswith(".png"):
            return True
        
        # Check exclusion patterns
        excluded_patterns = self.get_excluded_patterns()
        for pattern in excluded_patterns:
            # Simple pattern matching - could be enhanced with fnmatch
            if pattern.endswith("*"):
                if filepath.startswith(pattern[:-1]):
                    return False
            elif pattern.startswith("*"):
                if filepath.endswith(pattern[1:]):
                    return False
            else:
                if pattern in filepath:
                    return False
        
        # Check if it's an essential file
        essential_files = self.get_essential_files()
        for essential in essential_files:
            if essential.endswith("/"):
                # Directory pattern
                if filepath.startswith(essential):
                    return True
            elif essential.endswith("*"):
                # Wildcard pattern
                if filepath.startswith(essential[:-1]):
                    return True
            else:
                # Exact file
                if filepath == essential:
                    return True
        
        # Special check for encounter files
        if filepath.startswith("modules/encounters/encounter_") and filepath.endswith(".json"):
            return True
        
        # For full save mode, also check optional files
        if save_mode == "full":
            optional_files = self.get_optional_files()
            for optional in optional_files:
                if optional.endswith("/"):
                    if filepath.startswith(optional):
                        return True
                elif optional.endswith("*"):
                    if filepath.startswith(optional[:-1]):
                        return True
                else:
                    if filepath == optional:
                        return True
        
        return False
    
    def get_save_directory(self) -> str:
        """Get the save directory for the current module"""
        if not self.current_module:
            # Fallback to root saved_games directory
            return "saved_games"
        
        return f"modules/{self.current_module}/saved_games"
    
    def generate_save_metadata(self, description: str = "", save_mode: str = "essential") -> Dict[str, Any]:
        """Generate metadata for a save game"""
        timestamp = datetime.now()
        
        # Get current game state info
        party_info = {}
        location_info = {}
        
        try:
            party_tracker = safe_json_load("party_tracker.json")
            if party_tracker:
                party_info = {
                    "module": party_tracker.get("module", "Unknown"),
                    "party_members": party_tracker.get("partyMembers", []),
                    "party_npcs": len(party_tracker.get("partyNPCs", [])),
                    "current_location": party_tracker.get("worldConditions", {}).get("currentLocation", "Unknown"),
                    "current_area": party_tracker.get("worldConditions", {}).get("currentArea", "Unknown"),
                }
        except Exception as e:
            warning(f"FILE_OP: Could not load party tracker for metadata", category="save_game")
        
        try:
            current_location = safe_json_load("current_location.json")
            if current_location:
                location_info = {
                    "location_name": current_location.get("name", "Unknown"),
                    "area_id": current_location.get("areaId", "Unknown"),
                }
        except Exception as e:
            warning(f"FILE_OP: Could not load current location for metadata", category="save_game")
        
        # TABLETOP MODE: Generate worldline lineage fields for Many Worlds support
        save_id = str(uuid.uuid4())
        lineage_info = self._generate_lineage_info()
        
        metadata = {
            "save_timestamp": timestamp.isoformat(),
            "save_date_readable": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "description": description,
            "save_mode": save_mode,
            "module": self.current_module or "Unknown",
            # TABLETOP MODE: Worldline lineage fields
            "save_id": save_id,
            "worldline_id": lineage_info["worldline_id"],
            "lineage": {
                "parent_save_id": lineage_info["parent_save_id"],
                "parent_worldline_id": lineage_info["parent_worldline_id"],
                "fork_origin_save_id": lineage_info["fork_origin_save_id"],
                "created_after_restore": lineage_info["created_after_restore"],
            },
            "game_state": {
                **party_info,
                **location_info,
            },
            "system_info": {
                "save_format_version": "1.1",
                "created_by": "NeverEndingQuest Save System",
            }
        }
        
        return metadata
    
    def _generate_lineage_info(self) -> Dict[str, Any]:
        """Generate worldline lineage info for current save.
        
        TABLETOP MODE: Implements fork-on-first-save-after-restore behavior.
        """
        restore_context = self._load_restore_context()
        
        if restore_context and restore_context.get("pending_fork", False):
            worldline_id = str(uuid.uuid4())
            return {
                "worldline_id": worldline_id,
                "parent_save_id": restore_context.get("restored_save_id"),
                "parent_worldline_id": restore_context.get("restored_worldline_id"),
                "fork_origin_save_id": restore_context.get("restored_save_id"),
                "created_after_restore": True,
            }
        else:
            previous_worldline = self._get_current_worldline()
            return {
                "worldline_id": previous_worldline,
                "parent_save_id": None,
                "parent_worldline_id": None,
                "fork_origin_save_id": None,
                "created_after_restore": False,
            }
    
    def _get_current_worldline(self) -> str:
        """Get the current active worldline ID from most recent save or restore context.
        
        TABLETOP MODE: Caches worldline ID so sequential saves share the same worldline.
        """
        if self._current_worldline:
            return self._current_worldline
        
        restore_context = self._load_restore_context()
        if restore_context and restore_context.get("current_worldline_id"):
            self._current_worldline = restore_context["current_worldline_id"]
            return self._current_worldline
        
        saves = self.list_save_games()
        if saves:
            most_recent = saves[0]
            worldline = most_recent.get("worldline_id", str(uuid.uuid4()))
            self._current_worldline = worldline
            return self._current_worldline
        
        self._current_worldline = str(uuid.uuid4())
        return self._current_worldline
    
    def _load_restore_context(self) -> Optional[Dict[str, Any]]:
        """Load restore context from file for fork-on-first-save behavior."""
        try:
            if os.path.exists(RESTORE_CONTEXT_FILE):
                return safe_json_load(RESTORE_CONTEXT_FILE)
        except Exception as e:
            debug(f"Could not load restore context: {e}", category="save_game")
        return None
    
    def _save_restore_context(self, context: Dict[str, Any]) -> None:
        """Persist restore context for fork-on-first-save behavior."""
        try:
            os.makedirs(os.path.dirname(RESTORE_CONTEXT_FILE), exist_ok=True)
            safe_write_json(RESTORE_CONTEXT_FILE, context)
        except Exception as e:
            warning(f"Could not save restore context: {e}", category="save_game")
    
    def _clear_restore_context(self) -> None:
        """Clear restore context after fork has been applied."""
        try:
            if os.path.exists(RESTORE_CONTEXT_FILE):
                os.remove(RESTORE_CONTEXT_FILE)
        except Exception as e:
            debug(f"Could not clear restore context: {e}", category="save_game")
    
    def _export_memory_package(self, save_path: str) -> Optional[Dict[str, Any]]:
        """Export memory DB package into save directory.
        
        TABLETOP MODE: Creates memory_db_package/ subdirectory in save folder.
        Returns package info for metadata, or None if memory parity disabled.
        """
        if not MEMORY_PARITY_ENABLED:
            return {"status": "disabled", "message": "Memory parity not available"}
        
        if not os.path.exists(DEFAULT_MEMORY_DB_PATH):
            return {"status": "no_db", "message": "No memory DB to export"}
        
        package_dir = os.path.join(save_path, "memory_db_package")
        try:
            result = export_memory_db_package(
                DEFAULT_MEMORY_DB_PATH,
                package_dir,
                overwrite=True,
            )
            if result.get("status") == "success":
                info(f"FILE_OP: Exported memory package to {package_dir}", category="save_game")
            return result
        except Exception as e:
            error(f"FAILURE: Failed to export memory package: {e}", exception=e, category="save_game")
            return {"status": "error", "message": str(e)}
    
    def _preflight_validate_memory_package(self, save_path: str) -> Dict[str, Any]:
        """Preflight validation for memory package before restore mutations.
        
        TABLETOP MODE: Validates package integrity/compatibility before any
        restore file operations (backup, cleanup, copy) to ensure atomic failure.
        Returns validation result or legacy status if no package exists.
        """
        if not MEMORY_PARITY_ENABLED:
            return {"status": "disabled", "message": "Memory parity not available"}
        
        package_dir = os.path.join(save_path, "memory_db_package")
        
        if os.path.exists(package_dir) and os.path.isdir(package_dir):
            validation = validate_memory_package(package_dir)
            if validation.get("status") != "success":
                error(f"FAILURE: Memory package preflight validation failed: {validation.get('message')}", category="save_game")
                return {"status": "error", "message": validation.get("message")}
            return {"status": "success", "package_dir": package_dir, "preflight": True}
        else:
            return {"status": "legacy", "message": "No memory package - will use legacy fallback"}
    
    def _import_memory_package(self, save_path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Import memory package from save directory or apply legacy fallback.
        
        TABLETOP MODE: Handles three cases:
        1. Memory package exists -> import with validation (assumes preflight passed)
        2. Legacy save (no package) -> clean init fallback
        3. Memory parity disabled -> return disabled status
        """
        if not MEMORY_PARITY_ENABLED:
            return {"status": "disabled", "message": "Memory parity not available"}
        
        package_dir = os.path.join(save_path, "memory_db_package")
        
        if os.path.exists(package_dir) and os.path.isdir(package_dir):
            # Skip re-validation here - assume preflight passed
            try:
                result = import_memory_db_package(
                    package_dir,
                    DEFAULT_MEMORY_DB_PATH,
                    overwrite=True,
                )
                if result.get("status") == "success":
                    info(f"FILE_OP: Imported memory package from {package_dir}", category="save_game")
                return result
            except Exception as e:
                error(f"FAILURE: Failed to import memory package: {e}", exception=e, category="save_game")
                return {"status": "error", "message": str(e)}
        else:
            info(f"FILE_OP: Legacy save detected, initializing clean memory DB", category="save_game")
            success, message = self._init_clean_memory_db()
            if not success:
                return {"status": "error", "message": f"Legacy fallback failed: {message}"}
            return {"status": "legacy_fallback", "message": "Legacy save - clean memory init applied"}
    
    def _init_clean_memory_db(self) -> Tuple[bool, str]:
        """Initialize a clean memory DB for legacy save fallback.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if os.path.exists(DEFAULT_MEMORY_DB_PATH):
                os.remove(DEFAULT_MEMORY_DB_PATH)
            
            os.makedirs(os.path.dirname(DEFAULT_MEMORY_DB_PATH) or ".", exist_ok=True)
            
            if MEMORY_PARITY_ENABLED:
                from core.memory.memory_db import init_memory_db
                init_memory_db(DEFAULT_MEMORY_DB_PATH)
                info(f"FILE_OP: Initialized clean memory DB at {DEFAULT_MEMORY_DB_PATH}", category="save_game")
            return True, "Clean memory DB initialized successfully"
        except Exception as e:
            error_msg = f"Failed to initialize clean memory DB: {e}"
            error(f"FAILURE: {error_msg}", exception=e, category="save_game")
            return False, error_msg
    
    def _get_archive_additional_paths(self, metadata: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Resolve campaign-wide archive inclusion policy for played modules.
        
        TABLETOP MODE: Returns list of (file_path, archive_path) tuples for additional
        campaign artifacts required for cross-module recovery. Skips missing files safely.
        
        Determination of played modules:
        - Check campaign_archives/ and campaign_summaries/ for module-name patterns
        - Fallback to current module from metadata if no archives found
        - Include campaign-global continuity files
        
        Args:
            metadata: Save metadata with module info
            
        Returns:
            List of (source_path, archive_entry_path) tuples sorted for determinism
        """
        additional_paths = []
        
        try:
            # Determine played modules from campaign archives/summaries
            played_modules = set()
            
            # Check campaign_archives for module patterns: [Module_Name]_conversation_*.json
            archives_dir = "modules/campaign_archives"
            if os.path.exists(archives_dir) and os.path.isdir(archives_dir):
                for filename in os.listdir(archives_dir):
                    if filename.endswith("_conversation.json") or "_conversation_" in filename:
                        # Extract module name: Module_Name_conversation_*.json -> Module_Name
                        parts = filename.replace(".json", "").split("_")
                        if len(parts) >= 2:
                            # Reconstruct module name (may contain underscores)
                            module_name = "_".join(parts[:-1]) if parts[-1].isdigit() else "_".join(parts[:-2])
                            if module_name and module_name != "conversation":
                                played_modules.add(module_name)
            
            # Check campaign_summaries for module patterns: [Module_Name]_summary_*.json
            summaries_dir = "modules/campaign_summaries"
            if os.path.exists(summaries_dir) and os.path.isdir(summaries_dir):
                for filename in os.listdir(summaries_dir):
                    if filename.endswith("_summary.json") or "_summary_" in filename:
                        # Extract module name: Module_Name_summary_*.json -> Module_Name
                        parts = filename.replace(".json", "").split("_")
                        if len(parts) >= 2:
                            # Reconstruct module name (may contain underscores)
                            module_name = "_".join(parts[:-1]) if parts[-1].isdigit() else "_".join(parts[:-2])
                            if module_name and module_name != "summary":
                                played_modules.add(module_name)
            
            # Fallback to current module if no archives found
            if not played_modules:
                current_module = metadata.get("module") or self.current_module
                if current_module:
                    played_modules.add(current_module.replace(" ", "_"))
            
            # Include campaign-global continuity files (already in essential list but ensure coverage)
            campaign_global_files = [
                "modules/campaign.json",
                "modules/world_registry.json",
                "modules/effects_tracker.json",
                "modules/default/effects_tracker.json",
            ]
            
            for file_path in campaign_global_files:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    additional_paths.append((file_path, file_path))
            
            # Include campaign_archives and campaign_summaries directories
            for campaign_dir in ["modules/campaign_archives", "modules/campaign_summaries"]:
                if os.path.exists(campaign_dir) and os.path.isdir(campaign_dir):
                    for root, dirs, files in os.walk(campaign_dir):
                        # Sort for deterministic ordering
                        dirs.sort()
                        files.sort()
                        for filename in files:
                            file_path = os.path.join(root, filename)
                            arcname = os.path.relpath(file_path, ".")
                            additional_paths.append((file_path, arcname))
            
            # Sort all paths for deterministic zip entry ordering
            additional_paths.sort(key=lambda x: x[1])
            
            if played_modules:
                debug(f"CAMPAIGN_ARCHIVE: Resolved played modules: {sorted(played_modules)}", category="save_game")
            
        except Exception as e:
            # Log but don't fail - archive can proceed without additional paths
            warning(f"CAMPAIGN_ARCHIVE: Could not resolve additional paths: {e}", category="save_game")
        
        return additional_paths
    
    def _generate_archive_zip(self, save_path: str, metadata: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Generate archive zip for save folder.
        
        TABLETOP MODE: Helper for deterministic zip generation from save folder.
        Includes campaign-wide recovery artifacts for all played modules.
        Returns structured result for success/failure reporting.
        
        Args:
            save_path: Path to save folder directory
            metadata: Save metadata dict with save_id, save_timestamp, etc.
            
        Returns:
            Tuple of (success: bool, result: Dict)
            - Success: {
                "status": "success",
                "zip_path": "...",
                "zip_name": "...",
                "bytes": <int>
              }
            - Failure: {
                "status": "error",
                "message": "..."
              }
        """
        try:
            # Validate save_path exists and is directory
            if not os.path.exists(save_path):
                return False, {"status": "error", "message": f"Save path does not exist: {save_path}"}
            
            if not os.path.isdir(save_path):
                return False, {"status": "error", "message": f"Save path is not a directory: {save_path}"}
            
            # Create deterministic zip artifact name from metadata
            save_timestamp = metadata.get("save_timestamp", "")
            
            # Use timestamp as primary identifier (safe for filenames)
            if save_timestamp:
                # Parse ISO timestamp and create safe filename
                try:
                    dt = datetime.fromisoformat(save_timestamp.replace('Z', '+00:00'))
                    timestamp_safe = dt.strftime("%Y%m%d_%H%M%S")
                except Exception:
                    # Fallback: use raw timestamp with unsafe chars stripped
                    timestamp_safe = "".join(c for c in save_timestamp if c.isalnum() or c in "_-.")[:20]
            else:
                timestamp_safe = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Get save folder name and module for envelope preservation and naming
            save_folder_name = os.path.basename(save_path)
            
            # TABLETOP MODE: Build deterministic archive name with module/timestamp/save_folder
            # Format: archive_<module>_<timestamp>_<save_folder>.zip
            module_safe = (self.current_module or "unknown").replace(" ", "_")
            zip_name = f"archive_{module_safe}_{timestamp_safe}_{save_folder_name}.zip"
            
            # TABLETOP MODE: Export to root archive_exports/ directory for USB portability
            # This separates portable archives from module-specific save storage
            archive_exports_dir = self._get_archive_exports_directory()
            zip_path = os.path.join(archive_exports_dir, zip_name)
            
            # Preserve save_parent for envelope-relative path calculation
            # This is the parent of the save folder (module's saved_games/ directory)
            save_parent = os.path.dirname(os.path.abspath(save_path))
            
            # TABLETOP MODE: Resolve campaign-wide additional artifacts
            additional_paths = self._get_archive_additional_paths(metadata)
            
            # Check for memory_db_package in save folder
            memory_package_path = os.path.join(save_path, "memory_db_package")
            memory_package_present = os.path.exists(memory_package_path) and os.path.isdir(memory_package_path)
            
            # Build zip from save folder contents with envelope preservation
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # First: add save folder contents with envelope preservation
                    # Exclude memory_db_package from this pass - it will be added separately
                    save_entries = []
                    for root, dirs, files in os.walk(save_path):
                        # Skip memory_db_package directory in save folder walk
                        if "memory_db_package" in dirs:
                            dirs.remove("memory_db_package")
                        
                        # Sort for deterministic ordering
                        dirs.sort()
                        files.sort()
                        for filename in files:
                            file_path = os.path.join(root, filename)
                            # Calculate arcname preserving save folder envelope
                            # arcname includes save_folder_name as top-level directory
                            rel_path = os.path.relpath(file_path, save_parent)
                            save_entries.append((file_path, rel_path))
                    
                    # Sort save entries for determinism
                    save_entries.sort(key=lambda x: x[1])
                    for file_path, arcname in save_entries:
                        zf.write(file_path, arcname)
                    
                    # Second: add memory_db_package if present
                    if memory_package_present:
                        memory_entries = []
                        for root, dirs, files in os.walk(memory_package_path):
                            # Sort for deterministic ordering
                            dirs.sort()
                            files.sort()
                            for filename in files:
                                file_path = os.path.join(root, filename)
                                # Arcname preserves full path: save_folder/memory_db_package/...
                                rel_path = os.path.relpath(file_path, save_parent)
                                memory_entries.append((file_path, rel_path))
                        
                        # Sort memory entries for determinism
                        memory_entries.sort(key=lambda x: x[1])
                        for file_path, arcname in memory_entries:
                            try:
                                zf.write(file_path, arcname)
                            except Exception as e:
                                # Fail-closed: memory package write failure is critical
                                error_msg = f"Failed to add memory package file {file_path}: {e}"
                                error(f"FAILURE: {error_msg}", exception=e, category="save_game")
                                return False, {"status": "error", "message": error_msg}
                        
                        info(f"CAMPAIGN_ARCHIVE: Included memory_db_package in archive", category="save_game")
                    
                    # Third: add campaign-wide additional artifacts
                    for file_path, arcname in additional_paths:
                        if os.path.exists(file_path):
                            try:
                                zf.write(file_path, arcname)
                            except Exception as e:
                                # Log but continue - individual file failures shouldn't fail archive
                                warning(f"CAMPAIGN_ARCHIVE: Could not add {file_path}: {e}", category="save_game")
            except Exception as e:
                # Fail-closed: any zip creation failure returns error
                error_msg = f"Failed to create archive zip: {str(e)}"
                error(f"FAILURE: {error_msg}", exception=e, category="save_game")
                return False, {"status": "error", "message": error_msg}
            
            # Get actual zip file size
            zip_bytes = os.path.getsize(zip_path)
            
            info(f"FILE_OP: Generated archive zip: {zip_path} ({zip_bytes} bytes)", category="save_game")
            
            return True, {
                "status": "success",
                "zip_path": zip_path,
                "zip_name": zip_name,
                "bytes": zip_bytes
            }
            
        except Exception as e:
            error_msg = f"Failed to generate archive zip: {str(e)}"
            error(f"FAILURE: {error_msg}", exception=e, category="save_game")
            return False, {"status": "error", "message": error_msg}
    
    def _setup_restore_context(self, metadata: Dict[str, Any]) -> None:
        """Set up restore context for fork-on-first-save behavior.
        
        TABLETOP MODE: Persists context so next save knows to fork a new worldline.
        Also clears cached worldline to ensure new one is generated.
        """
        context = {
            "restored_save_id": metadata.get("save_id"),
            "restored_worldline_id": metadata.get("worldline_id"),
            "current_worldline_id": metadata.get("worldline_id"),
            "restore_timestamp": datetime.now().isoformat(),
            "pending_fork": True,
        }
        self._save_restore_context(context)
        self._current_worldline = None
    
    def create_save_game(self, description: str = "", save_mode: str = "essential") -> Tuple[bool, str]:
        """
        Create a save game with the specified mode.
        
        Args:
            description: User description for the save
            save_mode: "essential" for minimal save, "full" for complete save
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Generate timestamp for save directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_dir = self.get_save_directory()
            save_path = f"{save_dir}/save_{timestamp}"
            
            # Create save directory
            os.makedirs(save_path, exist_ok=True)
            info(f"FILE_OP: Created save directory: {save_path}", category="save_game")
            
            # Generate and save metadata
            metadata = self.generate_save_metadata(description, save_mode)
            metadata_path = f"{save_path}/save_metadata.json"
            if not safe_write_json(metadata_path, metadata):
                return False, "Failed to write save metadata"
            
            # Copy files based on save mode
            copied_files = []
            skipped_files = []
            
            # Walk through all files in the current directory
            for root, dirs, files in os.walk("."):
                # Skip the save directory itself
                if save_path in root:
                    continue
                
                # Skip any saved_games directories to prevent recursive nesting
                if "saved_games" in root or "save_20" in root:
                    continue
                
                # Skip directories that should be excluded
                dirs[:] = [d for d in dirs if not any(
                    d == "saved_games" or 
                    d.startswith("save_20") or
                    (d.startswith(pattern[:-1]) if pattern.endswith("*") else d == pattern)
                    for pattern in self.get_excluded_patterns() 
                    if "/" not in pattern
                )]
                
                # Process files
                for file in files:
                    file_path = os.path.join(root, file).replace("\\", "/")
                    # Remove leading ./
                    if file_path.startswith("./"):
                        file_path = file_path[2:]
                    
                    if self.should_include_file(file_path, save_mode):
                        # Copy this file
                        source_path = file_path
                        dest_path = f"{save_path}/{file_path}"
                        
                        # Ensure destination directory exists
                        dest_dir = os.path.dirname(dest_path)
                        if dest_dir:
                            os.makedirs(dest_dir, exist_ok=True)
                        
                        try:
                            shutil.copy2(source_path, dest_path)
                            copied_files.append(file_path)
                            debug(f"FILE_OP: Copied: {file_path}", category="save_game")
                        except Exception as e:
                            error(f"FAILURE: Failed to copy {file_path}", exception=e, category="save_game")
                            skipped_files.append(file_path)
                    else:
                        skipped_files.append(file_path)
            
            # Update metadata with file statistics
            metadata["file_statistics"] = {
                "files_copied": len(copied_files),
                "files_skipped": len(skipped_files),
                "total_files_processed": len(copied_files) + len(skipped_files),
            }

            # TABLETOP MODE: Export memory DB package for Many Worlds support
            memory_package_result = self._export_memory_package(save_path)
            if memory_package_result:
                metadata["memory_package"] = memory_package_result
            
            # TABLETOP MODE: Enforce explicit save failure if memory parity export fails
            if MEMORY_PARITY_ENABLED and os.path.exists(DEFAULT_MEMORY_DB_PATH):
                if memory_package_result and memory_package_result.get("status") == "error":
                    error_msg = f"Save failed: memory package export error - {memory_package_result.get('message', 'unknown error')}"
                    error(f"FAILURE: {error_msg}", category="save_game")
                    return False, error_msg

            # TABLETOP MODE: Confirm diary checkpoint only after save viability is established.
            # This keeps save failures from creating canon diary entries for aborted saves.
            diary_checkpoint_result = self._confirm_session_diary_checkpoint(metadata)
            metadata["session_diary"] = diary_checkpoint_result

            # TABLETOP MODE: Best-effort refresh of exported memory package after diary confirmation
            # so confirmed checkpoints are included in the saved memory snapshot when possible.
            diary_memory_refresh = None
            if (
                diary_checkpoint_result.get("status") == "success"
                and memory_package_result
                and memory_package_result.get("status") == "success"
            ):
                diary_memory_refresh = self._export_memory_package(save_path)
                metadata["session_diary_memory_refresh"] = diary_memory_refresh
                if diary_memory_refresh.get("status") != "success":
                    warning(
                        f"SESSION_DIARY: Memory package refresh degraded after diary checkpoint: {diary_memory_refresh.get('message', 'unknown error')}",
                        category="save_game",
                    )
            
            # Save updated metadata
            safe_write_json(metadata_path, metadata)
            
            # TABLETOP MODE: Clear restore context if this was a fork save
            if metadata.get("lineage", {}).get("created_after_restore", False):
                self._clear_restore_context()
                # Update restore context with new worldline for future saves
                self._save_restore_context({
                    "current_worldline_id": metadata["worldline_id"],
                    "pending_fork": False,
                    "last_save_id": metadata["save_id"],
                })
                # Cache the new worldline so subsequent saves share it
                self._current_worldline = metadata["worldline_id"]
            else:
                # Cache the worldline for non-fork saves too
                self._current_worldline = metadata["worldline_id"]
            
            success_msg = f"Save game created successfully: {save_path}"
            success_msg += f"\nCopied {len(copied_files)} files"
            if save_mode == "essential":
                success_msg += " (essential files only)"
            else:
                success_msg += " (full save)"

            diary_status = metadata.get("session_diary", {}).get("status")
            if diary_status == "success":
                success_msg += f"\nDiary checkpoint: {metadata['session_diary'].get('action', 'updated')}"
            elif diary_status:
                success_msg += f"\nDiary checkpoint: degraded ({diary_status})"
            
            # TABLETOP MODE: Add memory package status to success message
            if memory_package_result and memory_package_result.get("status") == "success":
                success_msg += f"\nMemory package: {memory_package_result.get('row_counts', {})}"
            
            info(f"SUCCESS: {success_msg}", category="save_game")
            return True, success_msg
            
        except Exception as e:
            error_msg = f"Failed to create save game: {str(e)}"
            error(f"FAILURE: {error_msg}", category="save_game")
            return False, error_msg
    
    def list_save_games(self) -> List[Dict[str, Any]]:
        """List all available save games with metadata"""
        save_dir = self.get_save_directory()
        save_games = []
        
        if not os.path.exists(save_dir):
            return save_games
        
        try:
            for item in os.listdir(save_dir):
                item_path = os.path.join(save_dir, item)
                if os.path.isdir(item_path) and item.startswith("save_"):
                    metadata_path = os.path.join(item_path, "save_metadata.json")
                    if os.path.exists(metadata_path):
                        metadata = safe_read_json(metadata_path)
                        if metadata:
                            metadata["save_folder"] = item
                            metadata["save_path"] = item_path
                            # TABLETOP MODE: Add convenience field for memory package presence
                            metadata["memory_package_present"] = os.path.exists(
                                os.path.join(item_path, "memory_db_package")
                            )
                            save_games.append(metadata)
        except Exception as e:
            error(f"FAILURE: Error listing save games", exception=e, category="save_game")
        
        # Sort by timestamp, newest first
        save_games.sort(key=lambda x: x.get("save_timestamp", ""), reverse=True)
        return save_games
    
    def restore_save_game(self, save_folder: str) -> Tuple[bool, str]:
        """
        Restore a save game by copying files back to the main game directory.
        
        Args:
            save_folder: Name of the save folder to restore
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            save_dir = self.get_save_directory()
            save_path = f"{save_dir}/{save_folder}"
            
            if not os.path.exists(save_path):
                return False, f"Save game not found: {save_path}"
            
            # Load save metadata
            metadata_path = f"{save_path}/save_metadata.json"
            metadata = safe_read_json(metadata_path)
            if not metadata:
                return False, "Could not read save game metadata"
            
            # TABLETOP MODE: Preflight validate memory package BEFORE any mutations
            preflight = self._preflight_validate_memory_package(save_path)
            if preflight.get("status") == "error":
                return False, f"Restore preflight failed: {preflight.get('message')}"

            # Delegate to shared restore pipeline
            success, message = self._execute_restore_core(save_path, metadata)

            # Preserve legacy caller-facing success headline
            if success:
                parts = message.split("\n", 1)
                tail = f"\n{parts[1]}" if len(parts) > 1 else ""
                message = f"Save game restored successfully from: {save_folder}{tail}"

            return success, message

        except Exception as e:
            error_msg = f"Failed to restore save game: {str(e)}"
            error(f"FAILURE: {error_msg}", category="save_game")
            return False, error_msg

    # TABLETOP MODE: Global save catalog for cross-module save discovery
    def list_save_games_global(self) -> List[Dict[str, Any]]:
        """List all save games across all modules with global discovery.

        Scans modules/*/saved_games/save_* for save folders and returns
        normalized metadata including source module and memory parity status.
        Entries sorted by save_timestamp descending (newest first).

        Returns:
            List of save metadata dictionaries with additive fields:
            - source_module: Module containing the save folder
            - save_folder: Folder name (e.g., save_20250216_143022)
            - save_path: Full path to save folder
            - memory_package_present: True if memory_db_package/ exists
            - All standard save metadata fields
        """
        save_games = []
        modules_base = "modules"

        if not os.path.exists(modules_base):
            return save_games

        try:
            for module_name in os.listdir(modules_base):
                module_path = os.path.join(modules_base, module_name)
                if not os.path.isdir(module_path):
                    continue

                save_dir = os.path.join(module_path, "saved_games")
                if not os.path.exists(save_dir):
                    continue

                for item in os.listdir(save_dir):
                    item_path = os.path.join(save_dir, item)
                    if not os.path.isdir(item_path) or not item.startswith("save_"):
                        continue

                    metadata_path = os.path.join(item_path, "save_metadata.json")
                    if not os.path.exists(metadata_path):
                        continue

                    metadata = safe_read_json(metadata_path)
                    if not metadata:
                        continue

                    # Add additive fields for global catalog
                    metadata["source_module"] = module_name
                    metadata["save_folder"] = item
                    metadata["save_path"] = item_path
                    metadata["memory_package_present"] = os.path.exists(
                        os.path.join(item_path, "memory_db_package")
                    )
                    save_games.append(metadata)

        except Exception as e:
            error(f"FAILURE: Error scanning global save games", exception=e, category="save_game")

        # Deterministic sort by timestamp descending (newest first)
        # Tie-break: source_module ascending, save_folder ascending for stability
        # Use two-pass stable sort: secondary keys first (asc), then primary (desc)
        save_games.sort(key=lambda x: (x.get("source_module", ""), x.get("save_folder", "")))
        save_games.sort(key=lambda x: x.get("save_timestamp", ""), reverse=True)
        return save_games

    def list_archive_exports(self) -> List[Dict[str, Any]]:
        """List archive zip artifacts from repo-root archive exports directory.

        TABLETOP MODE: Returns archive catalog entries for `archive_exports/*.zip`
        with deterministic sorting for load dialog integration.

        Returns:
            List of archive metadata dictionaries:
            - zip_name: Archive filename
            - zip_path: Absolute path to archive zip
            - bytes: File size in bytes
            - modified_timestamp: Last-modified time in ISO format
        """
        archive_entries = []
        archive_dir = self._get_archive_exports_directory()

        if not os.path.exists(archive_dir):
            return archive_entries

        try:
            for item in os.listdir(archive_dir):
                item_path = os.path.join(archive_dir, item)
                if not os.path.isfile(item_path):
                    continue

                if not item.lower().endswith(".zip"):
                    continue

                try:
                    modified_epoch = os.path.getmtime(item_path)
                    archive_entries.append({
                        "zip_name": item,
                        "zip_path": item_path,
                        "bytes": os.path.getsize(item_path),
                        "modified_timestamp": datetime.fromtimestamp(modified_epoch).isoformat(),
                        "_sort_epoch": modified_epoch,
                    })
                except OSError as file_error:
                    warning(
                        f"ARCHIVE_EXPORT: Could not inspect zip file {item}: {file_error}",
                        category="save_game",
                    )

        except Exception as e:
            error(f"FAILURE: Error listing archive exports", exception=e, category="save_game")

        # Deterministic sort: newest first, then filename ascending for stable ties
        archive_entries.sort(key=lambda x: x.get("zip_name", ""))
        archive_entries.sort(key=lambda x: x.get("_sort_epoch", 0), reverse=True)

        # Remove internal sort key from caller-facing payload
        for entry in archive_entries:
            entry.pop("_sort_epoch", None)

        return archive_entries

    def _resolve_archive_zip_path(self, zip_name: str) -> Tuple[bool, str]:
        """Resolve archive zip name to canonical path in archive exports directory.

        Args:
            zip_name: Archive zip filename (not a full path)

        Returns:
            Tuple of (is_valid: bool, result: str)
            - On success: (True, absolute_zip_path)
            - On failure: (False, error_message)
        """
        if not zip_name or not isinstance(zip_name, str):
            return False, "Invalid archive zip name: empty or not a string"

        if ".." in zip_name or "/" in zip_name or "\\" in zip_name:
            return False, "Invalid archive zip name: path traversal detected"

        if not zip_name.lower().endswith(".zip"):
            return False, "Invalid archive zip name: file must end with .zip"

        archive_dir = self._get_archive_exports_directory()
        zip_path = os.path.join(archive_dir, zip_name)

        if not os.path.exists(zip_path):
            return False, f"Archive zip not found: {zip_name}"

        if not os.path.isfile(zip_path):
            return False, f"Archive path is not a file: {zip_name}"

        return True, zip_path

    def _validate_archive_zip_preflight(self, zip_path: str) -> Tuple[bool, Dict[str, Any]]:
        """Validate archive zip structure, metadata, and traversal safety.

        Required checks:
        - Zip is readable and non-empty
        - No absolute/traversal entries
        - Exactly one top-level save folder metadata envelope
        - Source module resolves from metadata

        Args:
            zip_path: Absolute path to archive zip

        Returns:
            Tuple of (is_valid: bool, result: Dict)
            - On success: {
                "save_folder": str,
                "source_module": str,
                "metadata": Dict[str, Any],
                "metadata_entry": str,
              }
            - On failure: {"message": str}
        """
        if not zipfile.is_zipfile(zip_path):
            return False, {"message": "Invalid archive zip: not a zip file"}

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                members = zf.infolist()
                if not members:
                    return False, {"message": "Invalid archive zip: archive is empty"}

                metadata_entries: List[str] = []

                for member in members:
                    entry = member.filename.replace("\\", "/")

                    # Reject absolute paths and Windows drive roots
                    if entry.startswith("/") or entry.startswith("\\"):
                        return False, {"message": f"Invalid archive zip: absolute path entry '{entry}'"}
                    if len(entry) >= 2 and entry[1] == ":" and entry[0].isalpha():
                        return False, {"message": f"Invalid archive zip: absolute drive entry '{entry}'"}

                    # Reject traversal attempts
                    path_parts = [p for p in entry.split("/") if p and p != "."]
                    if any(part == ".." for part in path_parts):
                        return False, {"message": f"Invalid archive zip: traversal entry '{entry}'"}

                    # Envelope check: top-level save folder metadata only
                    if entry.endswith("/save_metadata.json") and entry.count("/") == 1:
                        metadata_entries.append(entry)

                if len(metadata_entries) != 1:
                    return False, {
                        "message": "Invalid archive zip: expected exactly one top-level save_metadata.json envelope"
                    }

                metadata_entry = metadata_entries[0]
                save_folder = metadata_entry.split("/", 1)[0]
                if not save_folder.startswith("save_"):
                    return False, {"message": f"Invalid archive zip: non-canonical save folder '{save_folder}'"}

                try:
                    metadata_raw = zf.read(metadata_entry)
                    metadata = json.loads(metadata_raw.decode("utf-8"))
                except Exception as metadata_error:
                    return False, {"message": f"Invalid archive zip metadata: {metadata_error}"}

                source_module = str(metadata.get("module", "")).strip()
                if not source_module or source_module.lower() == "unknown":
                    # Fallback to game_state.module for compatibility with older metadata variants
                    source_module = str(metadata.get("game_state", {}).get("module", "")).strip()

                source_module = source_module.replace(" ", "_")

                if not source_module or source_module.lower() == "unknown":
                    return False, {"message": "Invalid archive zip metadata: source module missing"}

                if ".." in source_module or "/" in source_module or "\\" in source_module:
                    return False, {"message": f"Invalid archive zip metadata: unsafe source module '{source_module}'"}

                module_dir = os.path.join("modules", source_module)
                if not os.path.isdir(module_dir):
                    return False, {"message": f"Source module not found for restore: {source_module}"}

                return True, {
                    "save_folder": save_folder,
                    "source_module": source_module,
                    "metadata": metadata,
                    "metadata_entry": metadata_entry,
                }

        except Exception as e:
            return False, {"message": f"Failed archive zip preflight validation: {str(e)}"}

    def _extract_archive_save_to_temp(self, zip_path: str, save_folder: str) -> Tuple[bool, Dict[str, Any]]:
        """Securely extract save envelope from zip into temporary staging directory.

        Args:
            zip_path: Absolute archive zip path
            save_folder: Envelope folder name to extract

        Returns:
            Tuple of (success: bool, result: Dict)
            - On success: {
                "temp_dir": str,
                "extracted_save_path": str,
              }
            - On failure: {"message": str}
        """
        temp_dir = tempfile.mkdtemp(prefix="neq_zip_restore_")
        extracted_save_path = os.path.join(temp_dir, save_folder)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                envelope_prefix = f"{save_folder}/"
                extracted_any = False

                for member in zf.infolist():
                    entry = member.filename.replace("\\", "/")
                    if not entry.startswith(envelope_prefix):
                        continue

                    relative_path = entry[len(envelope_prefix):]
                    if not relative_path:
                        continue

                    # Defense-in-depth path check during extraction
                    normalized_relative = os.path.normpath(relative_path)
                    if normalized_relative.startswith("..") or os.path.isabs(normalized_relative):
                        raise ValueError(f"Unsafe archive path during extraction: {entry}")

                    target_path = os.path.join(extracted_save_path, normalized_relative)

                    if member.is_dir() or entry.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                        continue

                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    with zf.open(member, "r") as source_stream:
                        with open(target_path, "wb") as target_stream:
                            shutil.copyfileobj(source_stream, target_stream)
                    extracted_any = True

            if not extracted_any:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False, {"message": "Archive extraction failed: save envelope contains no files"}

            metadata_path = os.path.join(extracted_save_path, "save_metadata.json")
            if not os.path.exists(metadata_path):
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False, {"message": "Archive extraction failed: save_metadata.json missing after extraction"}

            return True, {
                "temp_dir": temp_dir,
                "extracted_save_path": extracted_save_path,
            }

        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False, {"message": f"Archive extraction failed: {str(e)}"}

    def _stage_archive_save_folder(self, extracted_save_path: str, source_module: str, save_folder: str) -> Tuple[bool, str]:
        """Stage extracted save folder into canonical module save directory.

        Args:
            extracted_save_path: Path to extracted save folder in temp staging
            source_module: Canonical source module name
            save_folder: Save folder name

        Returns:
            Tuple of (success: bool, result: str)
            - On success: (True, canonical_staged_path)
            - On failure: (False, error_message)
        """
        try:
            if not os.path.isdir(extracted_save_path):
                return False, f"Staging failed: extracted save folder missing: {extracted_save_path}"

            module_save_dir = os.path.join("modules", source_module, "saved_games")
            os.makedirs(module_save_dir, exist_ok=True)

            staged_save_path = os.path.join(module_save_dir, save_folder)
            if os.path.exists(staged_save_path):
                return False, f"Staging failed: target save folder already exists: {staged_save_path}"

            shutil.copytree(extracted_save_path, staged_save_path)
            return True, staged_save_path

        except Exception as e:
            return False, f"Staging failed: {str(e)}"

    def restore_save_game_archive(self, zip_name: str) -> Tuple[bool, str]:
        """Restore a campaign save directly from a validated archive zip.

        Pipeline:
        1. Resolve zip in archive_exports/
        2. Preflight validate structure/metadata/safety
        3. Secure extract save envelope to temp staging
        4. Stage extracted save folder into canonical module save path
        5. Delegate to existing global folder restore pipeline
        """
        # Step 1: Resolve zip path from archive exports catalog
        zip_ok, zip_result = self._resolve_archive_zip_path(zip_name)
        if not zip_ok:
            return False, f"Archive restore validation failed: {zip_result}"

        zip_path = zip_result

        # Step 2: Preflight validation
        preflight_ok, preflight_result = self._validate_archive_zip_preflight(zip_path)
        if not preflight_ok:
            return False, f"Archive restore preflight failed: {preflight_result.get('message', 'unknown error')}"

        save_folder = preflight_result["save_folder"]
        source_module = preflight_result["source_module"]

        # Step 3: Secure extraction to temp staging
        extract_ok, extract_result = self._extract_archive_save_to_temp(zip_path, save_folder)
        if not extract_ok:
            return False, f"Archive restore extraction failed: {extract_result.get('message', 'unknown error')}"

        temp_dir = extract_result["temp_dir"]
        extracted_save_path = extract_result["extracted_save_path"]

        try:
            # Step 4: Stage save folder into canonical module save path
            stage_ok, stage_result = self._stage_archive_save_folder(
                extracted_save_path,
                source_module,
                save_folder,
            )
            if not stage_ok:
                return False, f"Archive restore staging failed: {stage_result}"

            info(
                f"ARCHIVE_EXPORT: Staged archive save '{save_folder}' for module '{source_module}'",
                category="save_game",
            )

            # Step 5: Delegate to existing global restore pipeline
            success, message = self.restore_save_game_global(source_module, save_folder)
            if success:
                message += f"\nArchive zip: {zip_name}"

            return success, message

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # TABLETOP MODE: Global restore routing and archive-zip restore helpers.

    def _validate_restore_target(self, module: str, save_folder: str) -> Tuple[bool, str]:
        """Validate cross-module restore target and return canonical path.

        Validates that module + save_folder resolve to an allowed save directory
        under modules/<module>/saved_games/save_*. Rejects path traversal attempts
        and malformed inputs.

        Args:
            module: Source module name (e.g., "Keep_of_Doom")
            save_folder: Save folder name (e.g., "save_20260216_143022")

        Returns:
            Tuple of (is_valid: bool, result: str)
            - On success: (True, canonical_save_path)
            - On failure: (False, error_message)
        """
        # Reject empty inputs
        if not module or not isinstance(module, str):
            return False, "Invalid module: empty or not a string"

        if not save_folder or not isinstance(save_folder, str):
            return False, "Invalid save_folder: empty or not a string"

        # Reject path traversal attempts
        if ".." in module or "/" in module or "\\" in module:
            return False, "Invalid module name: path traversal detected"

        if ".." in save_folder or "/" in save_folder or "\\" in save_folder:
            return False, "Invalid save folder name: path traversal detected"

        # Reject non-canonical save folder prefix
        if not save_folder.startswith("save_"):
            return False, "Invalid save folder: must start with 'save_'"

        # Construct canonical path
        save_path = os.path.join("modules", module, "saved_games", save_folder)

        # Verify path exists and is a directory
        if not os.path.exists(save_path):
            return False, f"Save folder not found: {save_path}"

        if not os.path.isdir(save_path):
            return False, f"Save path is not a directory: {save_path}"

        # Verify save_metadata.json exists
        metadata_path = os.path.join(save_path, "save_metadata.json")
        if not os.path.exists(metadata_path):
            return False, f"Save metadata not found: {metadata_path}"

        return True, save_path

    def _execute_restore_core(self, save_path: str, metadata: Dict[str, Any]) -> Tuple[bool, str]:
        """Execute core restore operations (backup, cleanup, copy, memory import).

        This is the shared restore implementation used by both legacy and global
        entrypoints. Assumes validation and preflight have already passed.

        Args:
            save_path: Validated full path to save folder
            metadata: Loaded save metadata dict

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Create backup of current state before restoring
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"modules/backups/restore_backup_{backup_timestamp}"

            info(f"FILE_OP: Creating backup before restore: {backup_dir}", category="save_game")

            # Copy current essential files to backup
            essential_files = self.get_essential_files()
            backed_up_files = []

            for essential in essential_files:
                if essential.endswith("/"):
                    # Directory
                    if os.path.exists(essential):
                        backup_dest = f"{backup_dir}/{essential}"
                        os.makedirs(os.path.dirname(backup_dest), exist_ok=True)
                        shutil.copytree(essential, backup_dest, dirs_exist_ok=True)
                        backed_up_files.append(essential)
                elif essential.endswith("*"):
                    # Wildcard pattern - find matching files
                    import glob
                    for match in glob.glob(essential):
                        if os.path.exists(match):
                            backup_dest = f"{backup_dir}/{match}"
                            os.makedirs(os.path.dirname(backup_dest), exist_ok=True)
                            shutil.copy2(match, backup_dest)
                            backed_up_files.append(match)
                else:
                    # Single file
                    if os.path.exists(essential):
                        backup_dest = f"{backup_dir}/{essential}"
                        os.makedirs(os.path.dirname(backup_dest), exist_ok=True)
                        shutil.copy2(essential, backup_dest)
                        backed_up_files.append(essential)

            # IMPORTANT: Clean directories that need to be fully replaced
            # This prevents orphaned files from remaining after restore
            directories_to_clean = [
                "modules/encounters/",  # Global encounters directory
                "characters/",  # Player/NPC characters
            ]

            # Add module-specific directories if we have a current module
            if self.current_module:
                module_base = f"modules/{self.current_module}"
                directories_to_clean.extend([
                    f"{module_base}/encounters/",
                    f"{module_base}/characters/",
                    f"{module_base}/areas/",
                    f"{module_base}/monsters/",
                ])

            # Clean each directory
            for directory in directories_to_clean:
                if os.path.exists(directory):
                    info(f"FILE_OP: Cleaning directory before restore: {directory}", category="save_game")
                    try:
                        # Remove all files in the directory EXCEPT BU files
                        for file in os.listdir(directory):
                            file_path = os.path.join(directory, file)
                            if os.path.isfile(file_path):
                                # CRITICAL: Preserve BU files during restore
                                if file.endswith("_BU.json"):
                                    debug(f"FILE_OP: Preserving BU file: {file_path}", category="save_game")
                                    continue
                                os.remove(file_path)
                                debug(f"FILE_OP: Removed: {file_path}", category="save_game")
                    except Exception as e:
                        warning(f"FILE_OP: Could not fully clean {directory}", category="save_game")

            # Now restore files from save
            restored_files = []
            failed_files = []

            # Walk through save directory and copy files back
            for root, dirs, files in os.walk(save_path):
                # TABLETOP MODE: Exclude memory_db_package from generic copy loop
                # Package is handled exclusively via managed import path
                if "memory_db_package" in dirs:
                    dirs.remove("memory_db_package")

                # Skip metadata file
                if "save_metadata.json" in files:
                    files.remove("save_metadata.json")

                for file in files:
                    source_file = os.path.join(root, file)
                    # Calculate relative path from save directory
                    rel_path = os.path.relpath(source_file, save_path)
                    dest_file = rel_path.replace("\\", "/")

                    try:
                        # Ensure destination directory exists
                        dest_dir = os.path.dirname(dest_file)
                        if dest_dir:
                            os.makedirs(dest_dir, exist_ok=True)

                        shutil.copy2(source_file, dest_file)
                        restored_files.append(dest_file)
                        debug(f"FILE_OP: Restored: {dest_file}", category="save_game")
                    except Exception as e:
                        error(f"FAILURE: Failed to restore {dest_file}", exception=e, category="save_game")
                        failed_files.append(dest_file)

            # TABLETOP MODE: Import memory package for Many Worlds support
            memory_result = self._import_memory_package(save_path, metadata)
            if memory_result.get("status") == "error":
                # Memory package exists but failed - fail the restore
                return False, f"Memory package restore failed: {memory_result.get('message')}"

            # TABLETOP MODE: Set up restore context for fork-on-first-save behavior
            self._setup_restore_context(metadata)

            success_msg = f"Save game restored successfully"
            success_msg += f"\nRestored {len(restored_files)} files"
            success_msg += f"\nBackup created: {backup_dir}"

            # TABLETOP MODE: Add memory package status to success message
            if memory_result.get("status") == "success":
                success_msg += f"\nMemory package: restored"
            elif memory_result.get("status") == "legacy_fallback":
                success_msg += f"\nMemory package: legacy fallback (clean init)"
            elif memory_result.get("status") == "disabled":
                success_msg += f"\nMemory package: parity disabled"

            if failed_files:
                success_msg += f"\nFailed to restore {len(failed_files)} files"

            info(f"SUCCESS: {success_msg}", category="save_game")
            return True, success_msg

        except Exception as e:
            error_msg = f"Failed to restore save game: {str(e)}"
            error(f"FAILURE: {error_msg}", exception=e, category="save_game")
            return False, error_msg

    def restore_save_game_global(self, module: str, save_folder: str) -> Tuple[bool, str]:
        """Restore a save game from any module with cross-module routing.

        Validates the target via Step 2.1 validator, then delegates to the shared
        restore pipeline to preserve safety invariants.

        Args:
            module: Source module containing the save
            save_folder: Name of the save folder to restore

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Step 1: Validate target (Step 2.1 validator)
        is_valid, result = self._validate_restore_target(module, save_folder)
        if not is_valid:
            return False, f"Restore validation failed: {result}"

        save_path = result

        # Step 2: Load metadata for preflight
        metadata_path = os.path.join(save_path, "save_metadata.json")
        metadata = safe_read_json(metadata_path)
        if not metadata:
            return False, "Could not read save game metadata"

        # Step 3: Memory preflight (must pass before any mutation)
        preflight = self._preflight_validate_memory_package(save_path)
        if preflight.get("status") == "error":
            return False, f"Restore preflight failed: {preflight.get('message')}"

        # Step 4: Delegate to shared restore pipeline using selected module context
        original_module = self.current_module
        try:
            self.current_module = module
            self.path_manager = ModulePathManager(module)
            success, message = self._execute_restore_core(save_path, metadata)
        finally:
            self.current_module = original_module
            if original_module:
                self.path_manager = ModulePathManager(original_module)
            else:
                self.path_manager = ModulePathManager()

        # Append source info to success message
        if success:
            message += f"\nSource module: {module}"
            message += f"\nSource folder: {save_folder}"

        return success, message

    def delete_save_game(self, save_folder: str) -> Tuple[bool, str]:
        """Delete a save game"""
        try:
            save_dir = self.get_save_directory()
            save_path = f"{save_dir}/{save_folder}"

            if not os.path.exists(save_path):
                return False, f"Save game not found: {save_path}"

            shutil.rmtree(save_path)
            info(f"SUCCESS: Deleted save game: {save_path}", category="save_game")
            return True, f"Save game deleted: {save_folder}"

        except Exception as e:
            error_msg = f"Failed to delete save game: {str(e)}"
            error(f"FAILURE: {error_msg}", category="save_game")
            return False, error_msg

# Example usage and testing
if __name__ == "__main__":
    # Test the save game manager
    manager = SaveGameManager()
    
    debug("INITIALIZATION: Testing Save Game Manager...", category="testing")
    
    # Test file categorization
    test_files = [
        "party_tracker.json",
        "debug.log", 
        "characters/player1.json",
        "modules/test_module/areas/area1.json",
        "test_file.py",
        "modules/conversation_history/conversation_history.json"
    ]
    
    debug("TEST: File categorization test:", category="testing")
    for test_file in test_files:
        essential = manager.should_include_file(test_file, "essential")
        full = manager.should_include_file(test_file, "full")
        debug(f"TEST: {test_file}: essential={essential}, full={full}", category="testing")
    
    # Test save game listing
    debug("TEST: Listing existing save games:", category="testing")
    saves = manager.list_save_games()
    for save in saves:
        debug(f"TEST: {save.get('save_folder', 'Unknown')}: {save.get('description', 'No description')}", category="testing")
    
    debug("SUCCESS: Save Game Manager test completed.", category="testing")
