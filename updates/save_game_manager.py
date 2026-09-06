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
import ntpath
import os
import shutil
import zipfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
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


def _lifecycle_wait_reporter(operation):
    last_second = [-1]

    def report(elapsed):
        second = max(0, int(elapsed))
        if second == last_second[0]:
            return
        last_second[0] = second
        from core.managers.status_manager import status_manager

        status_manager.update_status(
            "%s is waiting for a safe campaign boundary (%d seconds)"
            % (operation, second),
            True,
        )

    return report

# Versioned rules guidance ships with the application. It is never campaign
# state, and an older saved-game folder must not overwrite a newer installation.
APPLICATION_OWNED_REFERENCE_FILES = frozenset(
    (
        "data/spell_repository.json",
        "data/srd_common_rules.json",
    )
)


@dataclass(frozen=True)
class RestoreRequest:
    """In-memory handoff: stop the old gameplay stack before applying a Load."""

    manager: "SaveGameManager"
    save_folder: str


@dataclass(frozen=True)
class RestoreOutcome:
    """One Load's verified result; never a shared mutable last-result flag."""

    disposition: str
    message: str

    @property
    def can_resume(self) -> bool:
        return self.disposition in {"selected_applied", "previous_restored", "unchanged"}

    def as_legacy_tuple(self) -> Tuple[bool, str]:
        return self.disposition == "selected_applied", self.message


@contextmanager
def _active_combat_snapshot_lease(timeout_seconds=30.0, wait_callback=None):
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
        wait_callback=wait_callback,
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
        """Use the current party or the validated pending adventure selection."""
        self.current_module = None
        self.path_manager = None
        try:
            party_tracker = safe_json_load("party_tracker.json")
            if party_tracker:
                self.current_module = party_tracker.get("module", "").replace(" ", "_") or None
            if not self.current_module:
                from utils.startup_contract import parse_startup_checkpoint
                history = safe_json_load("modules/conversation_history/startup_conversation.json")
                progress = parse_startup_checkpoint(history or [])
                selected = progress.get("module") if progress else None
                # The catalog's exact installed-directory identity, not a path
                # supplied by arbitrary old history or the default module.
                if selected and os.path.isdir("modules") and selected in os.listdir("modules"):
                    if os.path.isdir(os.path.join("modules", selected)):
                        self.current_module = selected
            if self.current_module:
                self.path_manager = ModulePathManager(self.current_module)
        except Exception as e:
            warning(f"INITIALIZATION: Module context remains unselected: {e}", category="save_game")

    @staticmethod
    def _restore_io(operation, *args, cancel_check=None, **kwargs):
        """Retry a restore stage on typed temporary I/O, never permission prose."""
        from utils.path_transaction_lock import _wait_to_retry
        from utils.transient_filesystem import is_transient_filesystem_error

        started = time.monotonic()
        report = _lifecycle_wait_reporter('Load')
        while True:
            if cancel_check is not None:
                cancel_check()
            try:
                return operation(*args, **kwargs)
            except OSError as exc:
                if not is_transient_filesystem_error(exc):
                    raise
                _wait_to_retry(None, 0.05, report, started)

    @staticmethod
    def _clear_campaign_completion_metadata(*, generation_only=False) -> None:
        """Discard runtime WAL/receipts after restoring older campaign state."""
        campaign_file = os.path.abspath(
            os.path.normpath(os.path.join("modules", "campaign.json"))
        )
        metadata_dir = os.path.join(
            os.path.dirname(campaign_file),
            f".{os.path.basename(campaign_file)}.completion",
        )
        if generation_only:
            # Retire only producer work before backup. Ready intents belong to
            # already-published transitions and must survive with receipts in
            # the rollback preimage. Successful replacement clears both below.
            if os.path.isdir(metadata_dir):
                for name in os.listdir(metadata_dir):
                    path = os.path.join(metadata_dir, name)
                    if name.endswith(".work.json"):
                        os.remove(path)
            return
        SaveGameManager._clear_restore_directory(metadata_dir)

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

    @staticmethod
    def _restore_path_value(path):
        """Read a restore-owned node without following links out of the game."""
        if os.path.islink(path) or (hasattr(os.path, "isjunction") and os.path.isjunction(path)):
            raise ValueError("A restore path is a link, not owned campaign data")
        try:
            mode = os.stat(path).st_mode
        except FileNotFoundError:
            return ("absent", None)
        import stat

        if stat.S_ISDIR(mode):
            return ("directory", None)
        if stat.S_ISREG(mode):
            from utils.transient_filesystem import read_bytes_preserving_errors

            return ("file", read_bytes_preserving_errors(path))
        raise ValueError("A restore path is not a regular campaign file")

    @staticmethod
    def _restore_preserves_file(filename):
        return filename.endswith((".lock", "_BU.json")) or filename in {".gitkeep", ".gitignore"}

    @staticmethod
    def _clear_restore_directory(directory):
        """Remove replaceable contents; propagate failures and retain held locks."""
        if not os.path.exists(directory):
            return

        def walk_error(exc):
            raise exc

        for root, directories, files in os.walk(directory, topdown=False, onerror=walk_error):
            for filename in files:
                if SaveGameManager._restore_preserves_file(filename):
                    continue
                os.remove(os.path.join(root, filename))
            for name in directories:
                child = os.path.join(root, name)
                if not os.listdir(child):
                    os.rmdir(child)

    def _freeze_restore_inventory(self, save_path):
        """Freeze original membership/values before cleanup can change its inputs.

        Task 9: get_essential_files includes live globs and cannot be called
        again to reconstruct a preimage after failed multi-file application.
        This inventory lives only in this Load call, never in a new manifest.
        """
        import glob

        inventory = {}
        source_files = {}
        directory_roots = set()

        def record(path, *, recursive=False):
            path = os.path.normpath(path)
            if path in ("", "."):
                return
            if os.path.isabs(path) or ntpath.splitdrive(path)[0] or path.split(os.sep)[0] == "..":
                raise ValueError("A restore path is outside campaign data")
            parent = os.path.dirname(path)
            if parent:
                record(parent)
            if path not in inventory:
                inventory[path] = self._restore_path_value(path)
            if recursive and inventory[path][0] == "directory":
                directory_roots.add(path)
                with os.scandir(path) as entries:
                    for entry in entries:
                        # Lock identities are live authority, not snapshot data.
                        if not entry.name.endswith(".lock"):
                            record(entry.path, recursive=True)

        for essential in self.get_essential_files():
            for path in glob.glob(essential) if glob.has_magic(essential) else [essential]:
                record(path.rstrip("/"), recursive=True)
        for path in (
            "modules/encounters", "modules/.campaign.json.completion",
            "modules/conversation_history/pending_location_transition.json",
        ):
            record(path, recursive=True)

        def walk_error(exc):
            raise exc

        for root, directories, files in os.walk(save_path, onerror=walk_error):
            for directory in directories:
                source = os.path.join(root, directory)
                if os.path.islink(source) or (hasattr(os.path, "isjunction") and os.path.isjunction(source)):
                    raise ValueError("A saved directory is a link, not campaign data")
            for filename in files:
                relative = os.path.relpath(os.path.join(root, filename), save_path)
                normalized = relative.replace("\\", "/")
                if (
                    filename == "save_metadata.json"
                    or filename.endswith(".lock")
                    or normalized in APPLICATION_OWNED_REFERENCE_FILES
                    or normalized == "modules/.campaign.json.completion-epoch.json"
                    or normalized.startswith("modules/.campaign.json.completion/")
                    or normalized == "modules/conversation_history/pending_location_transition.json"
                ):
                    continue
                record(relative, recursive=True)
                source_files[relative] = self._restore_path_value(
                    os.path.join(save_path, relative)
                )
                if source_files[relative][0] != "file":
                    raise OSError("A selected save file changed during validation")
        # A top-level frozen tree already covers its descendants. Avoid
        # rescanning every nested directory during postcondition verification.
        roots = set(directory_roots)
        for path in directory_roots:
            parent = os.path.dirname(path)
            while parent:
                if parent in directory_roots:
                    roots.discard(path)
                    break
                parent = os.path.dirname(parent)
        return inventory, source_files, frozenset(roots)

    def _backup_restore_inventory(self, backup_dir, inventory):
        """Back up and verify every original node before any live mutation."""
        for relative, value in inventory.items():
            destination = os.path.join(backup_dir, relative)
            if value[0] == "directory":
                os.makedirs(destination, exist_ok=True)
            elif value[0] == "file":
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copy2(relative, destination)
                if self._restore_path_value(destination) != value:
                    raise OSError("The pre-restore backup did not match its source")

    def _restore_essential_backup(self, backup_dir: str, inventory, directory_roots) -> None:
        """Restore and verify the frozen preimage, never re-glob changed state."""
        # Descendants first: only remove nodes known to this operation. Unknown
        # new children make rmdir fail instead of silently deleting more data.
        for relative in sorted(inventory, key=lambda path: path.count(os.sep), reverse=True):
            wanted = inventory[relative]
            current = self._restore_path_value(relative)
            if current[0] != "absent" and current[0] != wanted[0]:
                if current[0] == "directory":
                    os.rmdir(relative)
                else:
                    os.remove(relative)
        for relative in sorted(inventory, key=lambda path: path.count(os.sep)):
            wanted = inventory[relative]
            if wanted[0] == "directory":
                os.makedirs(relative, exist_ok=True)
            elif wanted[0] == "file":
                source = os.path.join(backup_dir, relative)
                if self._restore_path_value(source) != wanted:
                    raise OSError("The rollback source no longer matches the original state")
                parent = os.path.dirname(relative)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                shutil.copy2(source, relative)
        if any(self._restore_path_value(path) != value for path, value in inventory.items()):
            raise OSError("The previous game state could not be verified after rollback")
        self._verify_restore_membership(inventory, directory_roots)

    @staticmethod
    def _verify_restore_membership(expected, directory_roots):
        """Reject unexplained children in frozen owned trees, excluding live locks."""
        def walk_error(exc):
            raise exc

        for directory in directory_roots:
            if not os.path.isdir(directory):
                continue  # Exact node-value verification owns absent/type checks.
            for root, directories, files in os.walk(directory, onerror=walk_error):
                for name in directories + files:
                    if name.endswith('.lock') and name in files:
                        continue
                    path = os.path.normpath(os.path.join(root, name))
                    if path not in expected or expected[path][0] == 'absent':
                        raise OSError('Unexpected state remains in a restored campaign directory')

    def _verify_selected_restore(self, original, source_files, directory_roots, clean_directories):
        """Verify replacement and retained values, including removed file absence."""
        clean = {os.path.normpath(path) for path in clean_directories}

        def replaced(path):
            return any(path == directory or path.startswith(directory + os.sep) for directory in clean)

        expected = dict(original)
        required_directories = {
            path for path, value in original.items()
            if value[0] == 'directory' and (path in clean or not replaced(path))
        }
        required_directories.update(map(os.path.normpath, (
            'modules/campaign_archives', 'modules/campaign_summaries',
        )))
        for path, value in original.items():
            if value[0] == 'file' and replaced(path) and not self._restore_preserves_file(os.path.basename(path)):
                expected[path] = ('absent', None)
        for path in ('modules/effects_state.json',
                     'modules/conversation_history/combat_conversation_history.json',
                     'modules/conversation_history/startup_conversation.json',
                     'modules/conversation_history/pending_location_transition.json'):
            path = os.path.normpath(path)
            if path not in source_files:
                expected[path] = ('absent', None)
        expected.update(source_files)
        for path, value in expected.items():
            if value[0] != 'file':
                continue
            parent = os.path.dirname(path)
            while parent:
                required_directories.add(parent)
                parent = os.path.dirname(parent)
        for directory in required_directories:
            expected[directory] = ('directory', None)
        for path, value in expected.items():
            current = self._restore_path_value(path)
            # Cleanup may remove an empty nested directory, but never a
            # required parent, retained tree, or selected file's container.
            if value[0] == 'directory' and replaced(path) and path not in required_directories:
                if current[0] in {'directory', 'absent'}:
                    continue
            if current != value:
                raise OSError('Selected save application could not be verified')
        self._verify_restore_membership(expected, set(directory_roots) | clean)
    
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
            "modules/conversation_history/startup_conversation.json",
            
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

    def _resolve_save_target(
        self, target: str, *, allow_missing: bool = False, receipt_path: bool = False
    ) -> str:
        """Resolve an owned save artifact, including native junction identity.

        Task 8: lexical containment alone did not protect direct deletes or
        persisted delete receipts. Missing targets are legal only for creation
        and replay of that receipt's completed rename/removal.
        """
        if not isinstance(target, str) or not target or "\0" in target:
            raise ValueError("Choose an existing save from the save list")
        if not receipt_path and (
            ntpath.splitdrive(target)[0]
            or target in (".", "..")
            or "/" in target
            or "\\" in target
        ):
            raise ValueError("Choose an existing save from the save list")
        if receipt_path and not os.path.isabs(target):
            raise ValueError("The delete receipt does not identify an owned save")

        def resolve_identity(path):
            # Resolve existing ancestors strictly: access/sharing failures must
            # not be mistaken for a proven absent resource or a safe link.
            missing = []
            while True:
                try:
                    identity = os.path.realpath(path, strict=True)
                    return os.path.join(identity, *reversed(missing))
                except FileNotFoundError:
                    parent, name = os.path.split(path)
                    if parent == path or not name or os.path.lexists(path):
                        raise
                    missing.append(name)
                    path = parent

        root = os.path.abspath(self.get_save_directory())
        candidate = os.path.abspath(
            target if receipt_path else os.path.join(root, target)
        )
        if os.path.commonpath(
            [os.path.normcase(root), os.path.normcase(candidate)]
        ) != os.path.normcase(root):
            raise ValueError("Choose an existing save from the save list")
        root_identity = os.path.normcase(resolve_identity(root))
        identity = os.path.normcase(resolve_identity(candidate))
        if (
            identity == root_identity
            or os.path.commonpath([root_identity, identity]) != root_identity
        ):
            raise ValueError("Choose an existing save from the save list")
        if os.path.lexists(candidate):
            if not os.path.isdir(candidate):
                raise ValueError("The referenced save is not a directory")
        elif not allow_missing:
            raise ValueError("The referenced save does not exist")
        return candidate

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
        """Settle completion outside snapshot locks; recheck at the boundary."""
        from core.managers.campaign_manager import (
            CampaignManager, _CampaignCompletionActive, _settle_campaign_completion_work,
        )
        from utils.capture.live_provider_call import (
            LiveProviderSuperseded, _interruptible_wait, get_live_provider_scope,
        )
        wait_reporter = _lifecycle_wait_reporter("Save")
        from utils.transient_filesystem import is_transient_filesystem_error

        try:
            while True:
                try:
                    outcome = CampaignManager(wait_callback=wait_reporter).drain_module_completion_intents(
                        wait_callback=wait_reporter,
                    )
                    if outcome["failed"]:
                        return False, "Cannot save: module completion could not be reconciled"
                    settled = _settle_campaign_completion_work(
                        "modules/campaign.json", wait_callback=wait_reporter,
                    )
                    if settled and not outcome["blocked"]:
                        return self._create_save_at_boundary(
                            description, save_mode, save_folder=save_folder,
                        )
                except _CampaignCompletionActive:
                    # New work appeared after settlement. Release and follow it.
                    pass
                except OSError as exc:
                    if not is_transient_filesystem_error(exc):
                        raise
                    # Retry only after all preparation/snapshot locks unwind.
                _interruptible_wait(0.25, get_live_provider_scope(),
                                    "Finishing the campaign record before saving...")
        except LiveProviderSuperseded:
            raise
        except Exception as exc:
            error("FAILURE: Could not settle the save boundary", exception=exc,
                  category="save_game")
            return False, f"Failed to create save game: {exc}"

    def _create_save_at_boundary(
        self,
        description: str = "",
        save_mode: str = "essential",
        *,
        save_folder: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Take one verified snapshot, or release its locks for settlement."""
        from core.managers.campaign_manager import _CampaignCompletionActive
        from utils.capture.live_provider_call import LiveProviderSuperseded
        try:
            from core.managers.campaign_manager import (
                _assert_no_active_campaign_completion,
                _campaign_transaction_lock,
                _party_module_transition_lock,
            )

            # Global lock order here is party transition -> active combat ->
            # module refresh -> campaign. Combat completion itself acquires
            # combat before module refresh, so this preserves that ordering.
            wait_reporter = _lifecycle_wait_reporter("Save")
            with _party_module_transition_lock(wait_callback=wait_reporter):
                # The manager may have been constructed before waiting for
                # this lock. A transition can commit in that interval, so
                # derive the save directory and metadata from the fresh party
                # projection inside the same serialized snapshot boundary.
                self._initialize_module_context()
                from utils.module_refresh_lock import module_refresh_lock

                with _active_combat_snapshot_lease(
                    timeout_seconds=None,
                    wait_callback=wait_reporter,
                ):
                    with module_refresh_lock(
                        max_wait_seconds=None,
                        wait_callback=wait_reporter,
                    ) as refresh_acquired:
                        if not refresh_acquired:
                            return False, "Module refresh is active; retry save"
                        # P2b: save no longer consults the module-lifecycle store.
                        # Module creation publishes atomically (build aside, one
                        # swap) and never leaves a half-built module live, so the
                        # live state is always safe to snapshot -- nothing to
                        # recover, nothing that can block a save.
                        with _campaign_transaction_lock(
                            "modules/campaign.json", wait_callback=wait_reporter
                        ):
                            _assert_no_active_campaign_completion(
                                "modules/campaign.json"
                            )
                            return self._create_save_game_locked(
                                description,
                                save_mode,
                                save_folder=save_folder,
                            )
        except (LiveProviderSuperseded, _CampaignCompletionActive):
            raise
        except Exception as exc:
            from utils.transient_filesystem import is_transient_filesystem_error

            if is_transient_filesystem_error(exc):
                raise
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
            if save_folder is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_folder = f"save_{timestamp}"
            if (
                not isinstance(save_folder, str)
                or not save_folder.startswith("save_")
            ):
                return False, "Invalid staged save folder"
            save_path = self._resolve_save_target(save_folder, allow_missing=True)
            metadata_path = f"{save_path}/save_metadata.json"
            if os.path.isdir(save_path):
                existing = safe_read_json(metadata_path)
                if (
                    isinstance(existing, dict)
                    and isinstance(existing.get("file_statistics"), dict)
                    and isinstance(existing.get("state_manifest"), list)
                ):
                    return True, f"Save game already exists: {save_path}"
                shutil.rmtree(save_path)
            
            # Create save directory
            os.makedirs(save_path, exist_ok=True)
            info(f"FILE_OP: Created save directory: {save_path}", category="save_game")
            
            # Generate and save metadata
            metadata = self.generate_save_metadata(description, save_mode)
            metadata_path = f"{save_path}/save_metadata.json"
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
                if os.path.commonpath([save_path, os.path.abspath(root)]) == save_path:
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
                try:
                    item_path = self._resolve_save_target(item)
                except (ValueError, FileNotFoundError):
                    continue
                if item.startswith("save_"):
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
        """Compatibility API; all restore behavior lives in the typed operation."""
        return self.restore_save_game_outcome(save_folder).as_legacy_tuple()

    def restore_save_game_outcome(
        self, save_folder: str, *, previous_clean: bool = True
    ) -> RestoreOutcome:
        """Replace one save timeline under the shared campaign boundary."""
        from core.combat.invocation import (
            begin_invocation_supersession,
            end_invocation_supersession,
        )

        invocation_barrier = begin_invocation_supersession("load")
        restore_outcome = None
        boundary_clean = previous_clean
        try:
            from core.managers.campaign_manager import (
                _bump_campaign_lifecycle_epoch,
                _campaign_transaction_lock,
                _party_module_transition_lock,
                _recover_campaign_completion_transaction_locked,
            )
            from utils.module_refresh_lock import module_refresh_lock

            wait_reporter = _lifecycle_wait_reporter("Load")
            with _party_module_transition_lock(wait_callback=wait_reporter):
                with _active_combat_snapshot_lease(
                    timeout_seconds=None,
                    wait_callback=wait_reporter,
                ):
                    with module_refresh_lock(
                        max_wait_seconds=None,
                        wait_callback=wait_reporter,
                    ) as refresh_acquired:
                        if not refresh_acquired:
                            raise OSError("Module refresh acquisition did not complete")
                        # P2b: restore no longer consults the module-lifecycle
                        # store. Loading a save must NEVER be refused -- a
                        # published module is already live on disk regardless of
                        # any leftover marker, and a missing creation narration is
                        # cosmetic. Fail-forward: always let the player load.
                        with _campaign_transaction_lock(
                            "modules/campaign.json", wait_callback=wait_reporter
                        ):
                            valid, validation_error = self.validate_restore_target(
                                save_folder,
                                include_manifest=False,
                            )
                            if not valid:
                                return RestoreOutcome(
                                    "unchanged" if previous_clean else "recovery_required",
                                    validation_error,
                                )
                            # Reconciliation can apply multiple canonical writes.
                            # Until preparation finishes, failure cannot certify
                            # that the original clean boundary still exists.
                            boundary_clean = False
                            self._restore_io(
                                _recover_campaign_completion_transaction_locked,
                                "modules/campaign.json", "modules/campaign_summaries",
                                "modules/campaign_archives",
                            )
                            _bump_campaign_lifecycle_epoch("modules/campaign.json")
                            # Generation records are retired authority, not
                            # clean gameplay state. Clear them before freezing
                            # the rollback preimage so failure cannot reinstall
                            # old work under the newly fenced timeline.
                            self._restore_io(self._clear_campaign_completion_metadata,
                                             generation_only=True)
                            boundary_clean = previous_clean
                            restore_outcome = self._restore_save_game_locked(
                                save_folder, previous_clean=previous_clean
                            )
            if restore_outcome.disposition != "selected_applied":
                return restore_outcome

            from core.npc.episodic_upgrade import (
                default_progress,
                repair_or_resume_canonical_memory,
            )

            repair = repair_or_resume_canonical_memory(progress=default_progress)
            if repair.get("status") == "error":
                warning(
                    "RESTORE: Companion memory remains resumable after selected "
                    "timeline restore",
                    category="save_game",
                )
            return restore_outcome
        except Exception as exc:
            error(
                "FAILURE: Could not establish consistent restore boundary",
                exception=exc,
                category="save_game",
            )
            # Companion-memory repair runs outside snapshot locks. Its failure
            # cannot erase an already verified disk disposition.
            return restore_outcome or RestoreOutcome(
                "unchanged" if boundary_clean else "recovery_required",
                f"Failed to restore save game: {exc}",
            )
        finally:
            end_invocation_supersession(invocation_barrier)

    def validate_restore_target(
        self,
        save_folder: str,
        include_manifest: bool = True,
        *,
        cancel_check=None,
    ) -> Tuple[bool, str]:
        """Validate one exact restore target without changing campaign state."""
        try:
            save_path = self._restore_io(
                self._resolve_save_target, save_folder, cancel_check=cancel_check,
            )
        except (ValueError, FileNotFoundError) as exc:
            return False, str(exc)
        metadata_path = os.path.join(save_path, 'save_metadata.json')
        kind, value = self._restore_io(
            self._restore_path_value, metadata_path, cancel_check=cancel_check,
        )
        try:
            metadata = json.loads(value) if kind == 'file' else None
        except (ValueError, UnicodeError):
            metadata = None
        if not metadata:
            return False, "Could not read save game metadata"
        if include_manifest:
            manifest_valid, manifest_error = self._validate_state_manifest(
                save_path,
                metadata,
            )
            if not manifest_valid:
                warning(
                    "RESTORE: State manifest diagnostic differs; continuing "
                    f"with the selected save: {manifest_error}",
                    category="save_game",
                )
        if cancel_check is not None:
            cancel_check()
        return True, ""

    def _restore_save_game_locked(
        self, save_folder: str, *, previous_clean: bool = True
    ) -> RestoreOutcome:
        """
        Restore a save game by copying files back to the main game directory.
        
        Args:
            save_folder: Name of the save folder to restore
            
        Returns:
            Verified selected, previous, unchanged, or recovery-required outcome.
        """
        backup_complete = False
        restore_mutation_started = False
        try:
            save_path = self._restore_io(self._resolve_save_target, save_folder)
            
            valid, validation_error = self.validate_restore_target(
                save_folder,
                include_manifest=True,
            )
            if not valid:
                return RestoreOutcome(
                    "unchanged" if previous_clean else "recovery_required",
                    validation_error,
                )

            original_inventory, source_files, directory_roots = self._restore_io(
                self._freeze_restore_inventory, save_path,
            )

            # Create backup of current state before restoring
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_dir = (
                "modules/backups/restore_backup_"
                f"{backup_timestamp}_{uuid4().hex}"
            )
            
            info(f"FILE_OP: Creating backup before restore: {backup_dir}", category="save_game")
            
            self._restore_io(self._backup_restore_inventory, backup_dir, original_inventory)

            backup_complete = True
            restore_mutation_started = True

            # Absence in an older save matters: re-detect effects migration,
            # never resume a later combat or an unrelated startup interview.
            # The verified backup retains these files for a failed-Load rollback.
            for optional_path in (
                "modules/effects_state.json",
                "modules/conversation_history/combat_conversation_history.json",
                "modules/conversation_history/startup_conversation.json",
            ):
                if os.path.normpath(optional_path) not in source_files:
                    try:
                        self._restore_io(os.remove, optional_path)
                    except FileNotFoundError:
                        pass
            
            # IMPORTANT: Clean directories that need to be fully replaced
            # This prevents orphaned files from remaining after restore
            for campaign_directory in (
                "modules/campaign_archives",
                "modules/campaign_summaries",
            ):
                self._restore_io(self._clear_restore_directory, campaign_directory)
                self._restore_io(os.makedirs, campaign_directory, exist_ok=True)

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
                    self._restore_io(self._clear_restore_directory, directory)
            
            # Now restore files from save
            for relative, expected in source_files.items():
                source_file = os.path.join(save_path, relative)
                parent = os.path.dirname(relative)
                if parent:
                    self._restore_io(os.makedirs, parent, exist_ok=True)
                self._restore_io(shutil.copy2, source_file, relative)
                if self._restore_io(self._restore_path_value, relative) != expected:
                    raise OSError("A restored file differs from the selected save")

            # Completion receipts describe the state that existed before this
            # restore.  Keeping them could suppress a valid transition from the
            # restored timeline, while a pending WAL could resurrect newer
            # campaign data on the next CampaignManager construction.
            self._restore_io(self._clear_campaign_completion_metadata)
            self._restore_io(self._clear_location_transition_runtime_marker)
            self._restore_io(self._verify_selected_restore,
                original_inventory, source_files, directory_roots,
                directories_to_clean + [
                    'modules/campaign_archives', 'modules/campaign_summaries',
                    'modules/.campaign.json.completion',
                ],
            )
            
            success_msg = f"Save game restored successfully from: {save_folder}"
            success_msg += f"\nRestored {len(source_files)} files"
            success_msg += f"\nBackup created: {backup_dir}"
            
            info(f"SUCCESS: {success_msg}", category="save_game")
            return RestoreOutcome("selected_applied", success_msg)
            
        except Exception as e:
            disposition = (
                "unchanged" if previous_clean and not restore_mutation_started
                else "recovery_required"
            )
            backup_path = locals().get("backup_dir")
            if (
                backup_complete
                and restore_mutation_started
                and isinstance(backup_path, str)
                and os.path.isdir(backup_path)
            ):
                disposition = "recovery_required"
                try:
                    self._restore_io(self._restore_essential_backup, backup_path, original_inventory, directory_roots)
                    if previous_clean:
                        disposition = "previous_restored"
                except Exception as rollback_exc:
                    error(
                        "FAILURE: Could not roll back campaign continuity after restore error",
                        exception=rollback_exc,
                        category="save_game",
                    )
            error_msg = f"Failed to restore save game: {str(e)}"
            error(f"FAILURE: {error_msg}", category="save_game")
            if disposition == "previous_restored":
                error_msg += "; previous game state was restored and verified"
            return RestoreOutcome(disposition, error_msg)
    
    def delete_save_game(self, save_folder: str) -> Tuple[bool, str]:
        """Delete a save game"""
        try:
            from core.managers.campaign_manager import _party_module_transition_lock

            with _party_module_transition_lock(
                wait_callback=_lifecycle_wait_reporter("Delete save")
            ):
                save_path = self._resolve_save_target(save_folder)
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
        target = self._resolve_save_target(save_folder)
        quarantine = self._resolve_save_target(
            ".delete-%s-%s" % (operation_id, save_folder), allow_missing=True
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
        from core.managers.campaign_manager import _party_module_transition_lock

        with _party_module_transition_lock(
            wait_callback=_lifecycle_wait_reporter("Delete save")
        ):
            target = self._resolve_save_target(
                receipt["target"], allow_missing=True, receipt_path=True
            )
            quarantine = self._resolve_save_target(
                receipt["quarantine"], allow_missing=True, receipt_path=True
            )
            expected = self._resolve_save_target(
                receipt["save_folder"], allow_missing=True
            )
            if (
                os.path.normcase(target) != os.path.normcase(expected)
                or os.path.normcase(os.path.dirname(quarantine))
                != os.path.normcase(os.path.dirname(target))
                or not os.path.basename(quarantine).startswith(".delete-")
                or not os.path.basename(quarantine).endswith("-" + receipt["save_folder"])
            ):
                raise ValueError("The delete receipt does not identify its staged save")
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
