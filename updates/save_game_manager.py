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
import hashlib
import os
import shutil
import zipfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4
# Import our existing utilities
from utils.file_operations import safe_write_json, safe_read_json
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

# Versioned rules guidance ships with the application. It is never campaign
# state, and an older saved-game folder must not overwrite a newer installation.
APPLICATION_OWNED_REFERENCE_FILES = frozenset(
    (
        "data/spell_repository.json",
        "data/srd_common_rules.json",
    )
)


@contextmanager
def _active_combat_snapshot_lease(timeout_seconds=30.0):
    """Keep a save/restore snapshot outside every combat commit window."""
    party = safe_json_load("party_tracker.json") or {}
    encounter_id = (party.get("worldConditions") or {}).get(
        "activeCombatEncounter"
    )
    encounter_path = (
        os.path.join("modules", "encounters", "encounter_%s.json" % encounter_id)
        if encounter_id
        else None
    )
    if not encounter_path or not os.path.isfile(encounter_path):
        yield
        return

    from utils.path_transaction_lock import path_transaction_lock

    with path_transaction_lock(
        encounter_path,
        suffix=".combat.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise RuntimeError("Combat is currently committing; retry this operation")
        yield

class SaveGameManager:
    """Manages save and restore operations for the Dungeon Master system"""
    
    def __init__(self):
        self.current_module = None
        self.path_manager = None
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

    @staticmethod
    def _clear_campaign_completion_metadata() -> None:
        """Discard runtime WAL/receipts after restoring older campaign state."""
        campaign_file = os.path.abspath(
            os.path.normpath(os.path.join("modules", "campaign.json"))
        )
        metadata_dir = os.path.join(
            os.path.dirname(campaign_file),
            f".{os.path.basename(campaign_file)}.completion",
        )
        if os.path.isdir(metadata_dir):
            shutil.rmtree(metadata_dir)

    @staticmethod
    def _clear_location_transition_runtime_marker() -> None:
        """Discard recovery authority belonging to the replaced timeline."""
        marker = os.path.join(
            "modules",
            "conversation_history",
            "pending_location_transition.json",
        )
        try:
            os.remove(marker)
        except FileNotFoundError:
            pass

    def _restore_essential_backup(self, backup_dir: str) -> None:
        """Restore the complete pre-restore projection after any copy failure."""
        import glob

        for essential in self.get_essential_files():
            if essential.endswith("/"):
                live_path = essential.rstrip("/")
                backup_path = os.path.join(backup_dir, live_path)
                if os.path.isdir(live_path):
                    shutil.rmtree(live_path)
                if os.path.isdir(backup_path):
                    parent = os.path.dirname(live_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    shutil.copytree(backup_path, live_path)
            elif essential.endswith("*"):
                for live_match in glob.glob(essential):
                    if os.path.isfile(live_match):
                        os.remove(live_match)
                backup_pattern = os.path.join(backup_dir, essential)
                for backup_match in glob.glob(backup_pattern):
                    relative = os.path.relpath(backup_match, backup_dir)
                    parent = os.path.dirname(relative)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    shutil.copy2(backup_match, relative)
            else:
                backup_path = os.path.join(backup_dir, essential)
                if os.path.isfile(backup_path):
                    parent = os.path.dirname(essential)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    shutil.copy2(backup_path, essential)
                elif os.path.isfile(essential):
                    os.remove(essential)
    
    def get_essential_files(self) -> List[str]:
        """Get list of essential files that must be saved for game state"""
        essential_files = [
            # Global state files
            "party_tracker.json",
            "current_location.json", 
            "journal.json",
            "player_storage.json",
            "data/companion_memories/",

            # Installed SRD reference data is application-owned, not campaign
            # state. Restoring an old save must never downgrade current rules.
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
            "modules/effects_state.json",
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
            "modules/.module_transactions/",
            "modules/.publication_transactions/",
            "modules/.module_orphan_quarantine/",
            "modules/.runtime_quarantine/",
            ".runtime_locks/",
            "modules/conversation_history/pending_location_transition.json",
            
            # CRITICAL: Exclude save directories to prevent recursive nesting
            "saved_games/",
            "*/saved_games/*",
            "save_20*",  # Exclude any save folders
            
            # Temporary files
            "*.tmp",
            "*.bak",
            "*.lock",
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

    # Private NPC state files fingerprinted in the save manifest (never by contents).
    _MANIFEST_STATE_PATHS = (
        "data/companion_memories/npc_agent_state.json",
        "data/companion_memories/episode_ledger.json",
        # W5: the one-time episodic-upgrade resume marker travels with save/restore so
        # a mid-upgrade save resumes correctly; skipped-if-absent keeps old saves valid.
        "data/companion_memories/episodic_upgrade.json",
    )

    @staticmethod
    def _state_manifest_for_root(root: str = ".") -> List[Dict[str, Any]]:
        """Describe private state files by fingerprint, never by contents."""
        entries: List[Dict[str, Any]] = []
        for relative_path in SaveGameManager._MANIFEST_STATE_PATHS:
            file_path = os.path.join(root, relative_path)
            if not os.path.isfile(file_path):
                continue
            try:
                with open(file_path, "rb") as handle:
                    raw = handle.read()
            except OSError:
                continue
            try:
                parsed = json.loads(raw.decode("utf-8"))
                schema_version = (
                    parsed.get("schemaVersion", -1)
                    if isinstance(parsed, dict)
                    else -1
                )
            except (UnicodeError, ValueError, TypeError):
                schema_version = -1
            entries.append(
                {
                    "path": relative_path,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "schemaVersion": schema_version,
                    "bytes": len(raw),
                }
            )
        return entries

    @staticmethod
    def _validate_state_manifest(
        save_path: str, metadata: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Validate every listed private state file before live mutation."""
        manifest = metadata.get("state_manifest")
        if manifest is None:
            return True, ""
        if not isinstance(manifest, list):
            return False, "state manifest is not a list"
        allowed_paths = set(SaveGameManager._MANIFEST_STATE_PATHS)
        for entry in manifest:
            if not isinstance(entry, dict) or set(entry) != {
                "path", "sha256", "schemaVersion", "bytes"
            }:
                return False, "state manifest entry is malformed"
            if entry["path"] not in allowed_paths:
                return False, "state manifest path is not recognized"
            candidate = os.path.join(save_path, entry["path"])
            try:
                with open(candidate, "rb") as handle:
                    raw = handle.read()
            except OSError:
                return False, "listed state file is missing"
            if len(raw) != entry["bytes"]:
                return False, "listed state file size differs"
            if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                return False, "listed state file hash differs"
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except (UnicodeError, ValueError, TypeError):
                return False, "listed state file is not JSON"
            # DEFECT-2 fix (T8f): the writer records -1 for files WITHOUT a
            # schemaVersion key (e.g. the episodic_upgrade marker), but
            # parsed.get() returns None for those same files here -- so every
            # save containing such a file failed its own restore validation
            # (a B1 violation: loading a save is NEVER refused). Normalize the
            # read exactly the way the writer does before comparing.
            observed_version = (
                parsed.get("schemaVersion", -1) if isinstance(parsed, dict) else -1
            )
            if observed_version is None:
                observed_version = -1
            if not isinstance(parsed, dict) or observed_version != entry["schemaVersion"]:
                return False, "listed state schema version differs"
        return True, ""

    def generate_save_metadata(self, description: str = "", save_mode: str = "essential") -> Dict[str, Any]:
        """Generate metadata for a save game"""
        timestamp = datetime.now()
        
        # Get current game state info
        party_info = {}
        location_info = {}
        
        try:
            party_tracker = safe_json_load("party_tracker.json")
            if party_tracker:
                world_conditions = party_tracker.get("worldConditions", {})
                party_info = {
                    "module": party_tracker.get("module", "Unknown"),
                    "party_members": party_tracker.get("partyMembers", []),
                    "party_npcs": len(party_tracker.get("partyNPCs", [])),
                    "current_location": world_conditions.get("currentLocation", "Unknown"),
                    "current_area": world_conditions.get("currentArea", "Unknown"),
                    "location_name": world_conditions.get("currentLocation", "Unknown"),
                    "location_id": world_conditions.get("currentLocationId", "Unknown"),
                    "area_id": world_conditions.get("currentAreaId", "Unknown"),
                }
        except Exception as e:
            warning(f"FILE_OP: Could not load party tracker for metadata", category="save_game")
        
        try:
            current_location = safe_json_load("current_location.json")
            if current_location:
                # party_tracker is authoritative after transitions. The
                # location snapshot is only a compatibility fallback when
                # tracker fields are absent.
                fallback_fields = {
                    "location_name": current_location.get("name", "Unknown"),
                    "location_id": current_location.get("locationId", "Unknown"),
                    "area_id": current_location.get("areaId", "Unknown"),
                }
                for key, value in fallback_fields.items():
                    if party_info.get(key) in (None, "", "Unknown"):
                        location_info[key] = value
        except Exception as e:
            warning(f"FILE_OP: Could not load current location for metadata", category="save_game")
        
        metadata = {
            "save_timestamp": timestamp.isoformat(),
            "save_date_readable": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "description": description,
            "save_mode": save_mode,
            "module": self.current_module or "Unknown",
            "game_state": {
                **party_info,
                **location_info,
            },
            "system_info": {
                "save_format_version": "1.0",
                "created_by": "NeverEndingQuest Save System",
            },
            "state_manifest": self._state_manifest_for_root(),
        }

        return metadata
    
    def create_save_game(
        self,
        description: str = "",
        save_mode: str = "essential",
        *,
        save_folder: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Drain committed transition intents, then snapshot under campaign lock."""
        try:
            from core.managers.campaign_manager import (
                CampaignManager,
                _assert_no_active_campaign_completion,
                _campaign_transaction_lock,
                _party_module_transition_lock,
            )

            # Global lock order here is party transition -> active combat ->
            # module refresh -> campaign. Combat completion itself acquires
            # combat before module refresh, so this preserves that ordering.
            # Hold the party lock while draining so no ready intent can appear
            # between the drain and the snapshot.
            with _party_module_transition_lock():
                drain_outcome = (
                    CampaignManager().drain_module_completion_intents()
                )
                if drain_outcome["failed"] or drain_outcome["blocked"]:
                    return (
                        False,
                        "Cannot save while a module completion remains queued",
                    )
                # The manager may have been constructed before waiting for
                # this lock. A transition can commit in that interval, so
                # derive the save directory and metadata from the fresh party
                # projection inside the same serialized snapshot boundary.
                self._initialize_module_context()
                from utils.module_refresh_lock import module_refresh_lock

                with _active_combat_snapshot_lease():
                    with module_refresh_lock() as refresh_acquired:
                        if not refresh_acquired:
                            return False, "Module refresh is active; retry save"
                        # P2b: save no longer consults the module-lifecycle store.
                        # Module creation publishes atomically (build aside, one
                        # swap) and never leaves a half-built module live, so the
                        # live state is always safe to snapshot -- nothing to
                        # recover, nothing that can block a save.
                        with _campaign_transaction_lock("modules/campaign.json"):
                            _assert_no_active_campaign_completion(
                                "modules/campaign.json"
                            )
                            return self._create_save_game_locked(
                                description,
                                save_mode,
                                save_folder=save_folder,
                            )
        except Exception as exc:
            error(
                "FAILURE: Could not establish consistent save boundary",
                exception=exc,
                category="save_game",
            )
            return False, f"Failed to create save game: {exc}"

    def _create_save_game_locked(
        self,
        description: str = "",
        save_mode: str = "essential",
        *,
        save_folder: Optional[str] = None,
    ) -> Tuple[bool, str]:
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
            save_dir = self.get_save_directory()
            if save_folder is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_folder = f"save_{timestamp}"
            if (
                not isinstance(save_folder, str)
                or not save_folder.startswith("save_")
                or os.path.basename(save_folder) != save_folder
                or any(separator in save_folder for separator in ("/", "\\"))
            ):
                return False, "Invalid staged save folder"
            save_path = os.path.join(save_dir, save_folder)
            metadata_path = f"{save_path}/save_metadata.json"
            if os.path.isdir(save_path):
                existing = safe_read_json(metadata_path)
                if (
                    isinstance(existing, dict)
                    and isinstance(existing.get("file_statistics"), dict)
                    and isinstance(existing.get("state_manifest"), dict)
                ):
                    return True, f"Save game already exists: {save_path}"
                shutil.rmtree(save_path)
            
            # Create save directory
            os.makedirs(save_path, exist_ok=True)
            info(f"FILE_OP: Created save directory: {save_path}", category="save_game")
            
            # Generate and save metadata
            metadata = self.generate_save_metadata(description, save_mode)
            if not safe_write_json(
                metadata_path, metadata, create_backup=False
            ):
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

            # Fingerprint the copied bytes, not a later live revision. This
            # keeps metadata and the save payload on the exact same timeline.
            metadata["state_manifest"] = self._state_manifest_for_root(save_path)

            # Save updated metadata
            if not safe_write_json(
                metadata_path, metadata, create_backup=False
            ):
                return False, "Failed to finalize save metadata"
            
            success_msg = f"Save game created successfully: {save_path}"
            success_msg += f"\nCopied {len(copied_files)} files"
            if save_mode == "essential":
                success_msg += " (essential files only)"
            else:
                success_msg += " (full save)"
            
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
                            save_games.append(metadata)
        except Exception as e:
            error(f"FAILURE: Error listing save games", exception=e, category="save_game")
        
        # Sort by timestamp, newest first
        save_games.sort(key=lambda x: x.get("save_timestamp", ""), reverse=True)
        return save_games
    
    def restore_save_game(self, save_folder: str) -> Tuple[bool, str]:
        """Replace one save timeline under the shared campaign boundary."""
        try:
            from core.managers.campaign_manager import (
                _assert_no_active_campaign_completion,
                _bump_campaign_lifecycle_epoch,
                _campaign_transaction_lock,
                _party_module_transition_lock,
            )
            from utils.module_refresh_lock import module_refresh_lock

            with _party_module_transition_lock():
                with _active_combat_snapshot_lease():
                    with module_refresh_lock() as refresh_acquired:
                        if not refresh_acquired:
                            return False, "Module refresh is active; retry restore"
                        # P2b: restore no longer consults the module-lifecycle
                        # store. Loading a save must NEVER be refused -- a
                        # published module is already live on disk regardless of
                        # any leftover marker, and a missing creation narration is
                        # cosmetic. Fail-forward: always let the player load.
                        with _campaign_transaction_lock("modules/campaign.json"):
                            save_path = os.path.join(
                                self.get_save_directory(),
                                save_folder,
                            )
                            if not os.path.isdir(save_path):
                                return False, f"Save game not found: {save_path}"
                            if not safe_read_json(
                                os.path.join(save_path, "save_metadata.json")
                            ):
                                return False, "Could not read save game metadata"
                            _assert_no_active_campaign_completion(
                                "modules/campaign.json"
                            )
                            _bump_campaign_lifecycle_epoch("modules/campaign.json")
                            return self._restore_save_game_locked(save_folder)
        except Exception as exc:
            error(
                "FAILURE: Could not establish consistent restore boundary",
                exception=exc,
                category="save_game",
            )
            return False, f"Failed to restore save game: {exc}"

    def _restore_save_game_locked(self, save_folder: str) -> Tuple[bool, str]:
        """
        Restore a save game by copying files back to the main game directory.
        
        Args:
            save_folder: Name of the save folder to restore
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        backup_complete = False
        restore_mutation_started = False
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

            manifest_valid, manifest_error = self._validate_state_manifest(
                save_path, metadata
            )
            if not manifest_valid:
                return (
                    False,
                    "State manifest integrity validation failed: "
                    f"{manifest_error}",
                )

            # Create backup of current state before restoring
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = (
                "modules/backups/restore_backup_"
                f"{backup_timestamp}_{uuid4().hex}"
            )
            
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

            backup_complete = True
            restore_mutation_started = True

            # A pre-V2 save intentionally has no effects_state.json.  Remove
            # the newer live stamp before copying so startup re-detects and
            # converts that restored timeline.  The rollback backup above
            # restores the stamp if any later restore step fails.
            saved_effects_state = os.path.join(
                save_path,
                "modules",
                "effects_state.json",
            )
            if not os.path.isfile(saved_effects_state):
                try:
                    os.remove("modules/effects_state.json")
                except FileNotFoundError:
                    pass
            
            # IMPORTANT: Clean directories that need to be fully replaced
            # This prevents orphaned files from remaining after restore
            for campaign_directory in (
                "modules/campaign_archives",
                "modules/campaign_summaries",
            ):
                if os.path.isdir(campaign_directory):
                    shutil.rmtree(campaign_directory)
                os.makedirs(campaign_directory, exist_ok=True)

            directories_to_clean = [
                "modules/encounters/",  # Global encounters directory
                "characters/",  # Player/NPC characters
                "data/companion_memories/",  # Private campaign runtime state
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
                                if directory == "data/companion_memories/":
                                    if (
                                        file not in {".gitkeep", ".gitignore"}
                                        and not file.endswith(".lock")
                                    ):
                                        os.remove(file_path)
                                        debug(f"FILE_OP: Removed: {file_path}", category="save_game")
                                    continue
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
                # Skip metadata file
                if "save_metadata.json" in files:
                    files.remove("save_metadata.json")
                
                for file in files:
                    source_file = os.path.join(root, file)
                    # Calculate relative path from save directory
                    rel_path = os.path.relpath(source_file, save_path)
                    dest_file = rel_path.replace("\\", "/")
                    if dest_file in APPLICATION_OWNED_REFERENCE_FILES:
                        debug(
                            "FILE_OP: Preserving installed reference data: "
                            f"{dest_file}",
                            category="save_game",
                        )
                        continue
                    
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

            if failed_files:
                # Restore the pre-restore continuity projection before
                # releasing the lifecycle locks. Existing WAL/intents/
                # receipts were retained, so they still describe this fully
                # rolled-back timeline.
                self._restore_essential_backup(backup_dir)
                return (
                    False,
                    "Save restore failed; previous game state was restored",
                )

            # Completion receipts describe the state that existed before this
            # restore.  Keeping them could suppress a valid transition from the
            # restored timeline, while a pending WAL could resurrect newer
            # campaign data on the next CampaignManager construction.
            self._clear_campaign_completion_metadata()
            self._clear_location_transition_runtime_marker()
            
            success_msg = f"Save game restored successfully from: {save_folder}"
            success_msg += f"\nRestored {len(restored_files)} files"
            success_msg += f"\nBackup created: {backup_dir}"
            
            if failed_files:
                success_msg += f"\nFailed to restore {len(failed_files)} files"
            
            info(f"SUCCESS: {success_msg}", category="save_game")
            return True, success_msg
            
        except Exception as e:
            backup_path = locals().get("backup_dir")
            if (
                backup_complete
                and restore_mutation_started
                and isinstance(backup_path, str)
                and os.path.isdir(backup_path)
            ):
                try:
                    self._restore_essential_backup(backup_path)
                except Exception as rollback_exc:
                    error(
                        "FAILURE: Could not roll back campaign continuity after restore error",
                        exception=rollback_exc,
                        category="save_game",
                    )
            error_msg = f"Failed to restore save game: {str(e)}"
            error(f"FAILURE: {error_msg}", category="save_game")
            return False, error_msg
    
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

    def prepare_staged_delete(
        self, save_folder: str, operation_id: str
    ) -> Dict[str, Any]:
        """Freeze one validated save target for a v2 deferred delete."""
        if (
            not isinstance(save_folder, str)
            or os.path.basename(save_folder) != save_folder
            or any(separator in save_folder for separator in ("/", "\\"))
        ):
            raise ValueError("Invalid save folder")
        save_dir = os.path.abspath(self.get_save_directory())
        target = os.path.abspath(os.path.join(save_dir, save_folder))
        if os.path.commonpath([save_dir, target]) != save_dir or not os.path.isdir(target):
            raise ValueError("The referenced save does not exist")
        quarantine = os.path.join(
            save_dir, ".delete-%s-%s" % (operation_id, save_folder)
        )
        if os.path.exists(quarantine):
            raise ValueError("A delete quarantine already exists for this operation")
        return {
            "kind": "deleteSave",
            "save_folder": save_folder,
            "target": target,
            "quarantine": quarantine,
        }

    def apply_staged_delete(self, receipt: Dict[str, Any]) -> str:
        """Rename then remove only the exact pre-staged save directory."""
        target = receipt["target"]
        quarantine = receipt["quarantine"]
        target_exists = os.path.isdir(target)
        quarantine_exists = os.path.isdir(quarantine)
        if target_exists and quarantine_exists:
            return "blocked_conflict"
        if target_exists:
            os.replace(target, quarantine)
            quarantine_exists = True
        if quarantine_exists:
            shutil.rmtree(quarantine)
        return "committed"

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
