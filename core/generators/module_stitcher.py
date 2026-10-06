# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Module Stitcher
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# MODULE_STITCHER.PY - ORGANIC MODULE INTEGRATION AND WORLD BUILDING
# ============================================================================
# 
# ARCHITECTURE ROLE: Module Integration Layer - Automatic Community Module Stitching
# 
# This module implements an organic module integration system that automatically
# detects, analyzes, and connects adventure modules based on their actual content.
# It uses AI-driven analysis of area descriptions, plot themes, and existing
# connectivity to suggest natural narrative bridges between modules.
# 
# CORE DESIGN PHILOSOPHY - ISOLATED MODULE ARCHITECTURE:
# - Each module is self-contained and independent
# - AI generates travel narration for clean transitions between modules
# - No cross-module area connections to prevent state management issues
# - Uses current data structure (area files, plot files) not outdated module.json
# - Community-ready for player-made and downloaded modules
# 
# SAFETY & CONFLICT RESOLUTION:
# - Automatic ID conflict resolution (area IDs, location IDs)
# - File structure security validation (no executables, size limits)
# - AI content safety review (family-friendly validation)
# - Schema compliance checking (80% minimum pass rate)
# - Graceful error handling with detailed logging
# 
# ID CONFLICT RESOLUTION:
# - Detects duplicate area IDs (e.g., HH001 already exists)
# - Generates unique alternatives (HH001 → HH002)
# - Updates all references: area files, location IDs, map connections
# - Renames corresponding files automatically
# - Preserves data integrity throughout process
# 
# CONTENT SAFETY VALIDATION:
# - File security: blocks executables, oversized files, directory traversal
# - AI content review: checks for inappropriate themes or content
# - Schema validation: ensures JSON structure compliance
# - Rejects modules that fail security or safety checks
# 
# DATA SOURCES (CURRENT ARCHITECTURE):
# - Area files (HH001.json, G001.json, etc.) - area descriptions and connectivity
# - module_plot.json - story themes and main objectives  
# - map_*.json files - layout information (source of truth)
# - areaConnectivity fields - existing connections between areas
# 
# KEY RESPONSIBILITIES:
# - Scan modules/ directory for new modules on startup
# - Resolve ID conflicts automatically before integration
# - Validate module safety using multiple security layers
# - Extract area metadata from current file structure
# - AI analysis of area themes and compatibility
# - Generate simple narrative transition bridges
# - Build organic world registry that grows with each module
# - Auto-register valid modules in campaign system
# 
# INTEGRATION WORKFLOW:
# 1. Detect new modules by scanning directory structure
# 2. Check for ID conflicts and resolve automatically
# 3. Validate module safety (files, content, schemas)
# 4. Extract area data from *.json files (not module.json)
# 5. Analyze themes using module_plot.json content
# 6. Generate AI travel narration for clean module transitions
# 7. Update world registry with isolated modules
# 8. Store travel narration for seamless switching
# 
# EXAMPLE ISOLATED MODULES:
# Keep_of_Doom: Harrow's Hollow → Gloamwood → Shadowfall Keep (self-contained)
# + Crystal_Peaks: Frostspire Village → Ice Caverns (independent module)
# = AI Travel Narration: "The party travels through mountain passes to reach the frozen peaks where new dangers await..."
# 
# SAFETY CONFIGURATION:
# - MAX_FILE_SIZE: 10MB per file limit
# - MIN_SCHEMA_SUCCESS_RATE: 80% validation threshold
# - Dangerous patterns: executables, scripts, directory traversal blocked
# - AI safety model: Uses DM_SUMMARIZATION_MODEL for content review
# 
# This creates a safe, modular adventure system where each module is independent
# but connected through AI-generated travel narration, maintaining security and
# data integrity while preventing cross-module state management issues.
# ============================================================================

import json
import os
import glob
import re
import hashlib
import errno
import shutil
import stat
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from uuid import uuid4
from core.ai import api_client
import config
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T032", "core/generators/module_stitcher.py", 1450)
register_callsite("T033", "core/generators/module_stitcher.py", 4016)

# Set script name for logging
set_script_name("module_stitcher")
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.transient_filesystem import (
    is_transient_filesystem_error,
    read_bytes_preserving_errors,
    replace_target_is_read_only,
)
from utils.module_path_manager import ModulePathManager


# Cache native capability facts before tests/instrumentation wrap os functions.
# Membership checks against the wrapped function objects would otherwise turn
# security tests into vacuous preflight failures.
_OPEN_SUPPORTS_DIR_FD = os.open in getattr(os, "supports_dir_fd", set())
_MKDIR_SUPPORTS_DIR_FD = os.mkdir in getattr(os, "supports_dir_fd", set())
_STAT_SUPPORTS_DIR_FD = os.stat in getattr(os, "supports_dir_fd", set())
_STAT_SUPPORTS_NOFOLLOW = os.stat in getattr(
    os, "supports_follow_symlinks", set()
)
_LISTDIR_SUPPORTS_FD = os.listdir in getattr(os, "supports_fd", set())
_UNLINK_SUPPORTS_DIR_FD = os.unlink in getattr(os, "supports_dir_fd", set())
_RENAME_SUPPORTS_DIR_FD = os.rename in getattr(os, "supports_dir_fd", set())


def _windows_held_handles_supported() -> bool:
    """Whether native Windows entries can be held by handle (issue #608)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        import msvcrt
    except ImportError:
        return False
    return hasattr(ctypes, "WinDLL") and hasattr(msvcrt, "open_osfhandle")


def _open_windows_no_follow(path: str, *, directory: bool) -> int:
    """Hold one native Windows entry without following a link (issue #608).

    FILE_FLAG_OPEN_REPARSE_POINT opens a junction or symlink as itself, the
    O_NOFOLLOW counterpart. Directories ask for FILE_LIST_DIRECTORY: an open
    with attribute access alone was observed not to block a rename.
    FILE_SHARE_DELETE is withheld, so while the handle is held the entry and
    its ancestors cannot be renamed or deleted; its children still can, and
    other processes may still write a held file. Returns a CRT descriptor.
    Every failure is an OSError, so callers type it like any other I/O error.
    """
    try:
        import ctypes
        from ctypes import wintypes
        import msvcrt

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = (
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        )
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel.CloseHandle.restype = wintypes.BOOL
        if directory:
            access = 0x0001 | 0x0080  # FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES
            flags = 0x00200000 | 0x02000000  # OPEN_REPARSE_POINT | BACKUP_SEMANTICS
        else:
            access = 0x80000000  # GENERIC_READ
            flags = 0x00200000  # FILE_FLAG_OPEN_REPARSE_POINT
        handle = kernel.CreateFileW(
            os.fsdecode(path),
            access,
            1 | 2,  # FILE_SHARE_READ | FILE_SHARE_WRITE; no FILE_SHARE_DELETE
            None, 3, flags, None,  # non-inherited, OPEN_EXISTING
        )
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return msvcrt.open_osfhandle(
                handle, os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT
            )
        except BaseException:
            kernel.CloseHandle(handle)
            raise
    except OSError:
        raise
    except Exception as exc:
        raise OSError(f"Windows entry could not be held: {exc}") from exc


def _windows_final_path(descriptor: int) -> str:
    """Return a held Windows entry's own path (issue #608).

    The path is read from the handle in \\\\?\\Volume{...} form: junctions on
    the way are resolved, so every component is a real directory that the
    held handle pins, and the prefix turns off Win32 name rewriting (a
    trailing dot or space is kept). Children are named through it.
    """
    try:
        import ctypes
        from ctypes import wintypes
        import msvcrt

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetFinalPathNameByHandleW.argtypes = (
            wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
        )
        kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        handle = msvcrt.get_osfhandle(descriptor)
        size = 32768  # the longest Windows path, 32767 characters, plus NUL
        buffer = ctypes.create_unicode_buffer(size)
        length = kernel.GetFinalPathNameByHandleW(
            handle, buffer, size, 0x1  # FILE_NAME_NORMALIZED | VOLUME_NAME_GUID
        )
        if length == 0 or length >= size:
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.value
    except OSError:
        raise
    except Exception as exc:
        raise OSError(f"Held entry path could not be read: {exc}") from exc


class ModuleSafetyStatus(str, Enum):
    """Outcome of the module safety-validation pipeline.

    ``UNAVAILABLE`` deliberately differs from ``UNSAFE``: the former means no
    policy verdict was produced (for example, malformed JSON or a provider
    outage), while the latter is an actual rejection.  Only ``SAFE`` may pass
    the integration gate.
    """

    SAFE = "safe"
    UNSAFE = "unsafe"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ModuleSafetyResult:
    """Typed safety result used to prevent unavailable checks looking safe."""

    status: ModuleSafetyStatus
    reason: str = ""

    @property
    def allows_integration(self) -> bool:
        return self.status is ModuleSafetyStatus.SAFE

    def __bool__(self) -> bool:
        raise TypeError(
            "ModuleSafetyResult has no implicit truth value; inspect .status "
            "or .allows_integration explicitly"
        )


class PublicationStatus(str, Enum):
    """Exact outcome of one targeted module-publication attempt."""

    PUBLISHED = "PUBLISHED"
    NOT_PUBLISHED = "NOT_PUBLISHED"
    IMPORT_REQUIRED = "IMPORT_REQUIRED"
    INDETERMINATE = "INDETERMINATE"


class NotJoinedCause(str, Enum):
    """Why an installed module was not joined, for the startup line."""

    # A check on this module's files or content refused it. This includes
    # local errors a check swallows (issue #639).
    CHECK_REFUSED = "check_refused"
    # The safety check produced no verdict (UNAVAILABLE).
    CHECK_UNAVAILABLE = "check_unavailable"
    # Scan entry only, never a result's cause: publication was
    # INDETERMINATE and the registry on disk does not join the module
    # (issue #608).
    UNPROVEN = "unproven"
    # Scan entry only, never a result's cause: as UNPROVEN, while the
    # registry file is read-only, so no module can join (issue #654).
    REGISTRY_READ_ONLY = "registry_read_only"


@dataclass(frozen=True)
class TargetedPublicationResult:
    """Proof-bearing result for publishing one exact module directory.

    ``NOT_PUBLISHED`` is returned only when the registry is proven not to
    reference the module and the live module is proven to match the manifest
    of the held tree taken before validation.
    ``INDETERMINATE`` means cleanup is unsafe because at least one relevant
    on-disk state could not be proven.

    ``backup_path`` is a compatibility-shaped, permanently ``None`` field.
    The manifest receipt deliberately exposes no mutable filesystem locator.
    """

    status: PublicationStatus
    module_name: str
    reason: str = ""
    registry_absence_proven: bool = False
    registry_restoration_proven: bool = False
    module_restoration_proven: bool = False
    backup_path: Optional[str] = field(default=None, init=False, repr=False)
    # IMPORT_REQUIRED only: the registered modules whose ids collide.
    conflicting_modules: Tuple[str, ...] = ()
    # NOT_PUBLISHED only, and only where the refusing check is known.
    cause: Optional[NotJoinedCause] = None

    @property
    def published(self) -> bool:
        return self.status is PublicationStatus.PUBLISHED

    @property
    def cleanup_safe(self) -> bool:
        return (
            self.status is PublicationStatus.NOT_PUBLISHED
            and self.registry_absence_proven is True
            and self.registry_restoration_proven is True
            and self.module_restoration_proven is True
        )

    def cleanup_safe_for(self, expected_module_name: str) -> bool:
        """Bind complete non-publication proof to the exact builder result."""
        return (
            self.module_name == expected_module_name
            and self.cleanup_safe is True
        )

    def __bool__(self) -> bool:
        raise TypeError(
            "TargetedPublicationResult has no implicit truth value; inspect "
            ".status, .published, or .cleanup_safe explicitly"
        )


@dataclass(frozen=True)
class RegistryAbsenceResult:
    """Fresh-disk proof used to decide whether orphan cleanup is safe."""

    module_name: str
    proven: bool
    absent: bool
    reason: str = ""

    @property
    def cleanup_safe(self) -> bool:
        return self.proven is True and self.absent is True

    def __bool__(self) -> bool:
        raise TypeError(
            "RegistryAbsenceResult has no implicit truth value; inspect "
            ".proven, .absent, or .cleanup_safe explicitly"
        )


class OrphanCleanupStatus(str, Enum):
    """Exact outcome of proof-bound unpublished-module cleanup."""

    REMOVED = "REMOVED"
    ALREADY_ABSENT = "ALREADY_ABSENT"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


@dataclass(frozen=True)
class OrphanCleanupResult:
    """Typed cleanup result that cannot be mistaken for an arbitrary boolean."""

    status: OrphanCleanupStatus
    module_name: str
    reason: str = ""
    quarantine_path: Optional[str] = None

    @property
    def safe_to_retry(self) -> bool:
        return (
            self.status is OrphanCleanupStatus.REMOVED
            or self.status is OrphanCleanupStatus.ALREADY_ABSENT
        )

    def safe_to_retry_for(self, expected_module_name: str) -> bool:
        """Bind a retry-safe status to the exact generated module."""
        return (
            self.module_name == expected_module_name
            and self.safe_to_retry is True
        )

    def __bool__(self) -> bool:
        raise TypeError(
            "OrphanCleanupResult has no implicit truth value; inspect .status "
            "or .safe_to_retry explicitly"
        )


@dataclass(frozen=True)
class _ExactModuleEntryGuard:
    """Held no-follow identity for one cooperative publication transaction."""

    module_name: str
    module_path: str
    descriptor: int
    identity: Tuple[int, int, int]
    # The path the manifest names children through: module_path on POSIX,
    # the held handle's final path on native Windows (#608).
    held_path: Optional[str] = None


@dataclass(frozen=True)
class _ModuleBackupResult:
    """Identity-bound manifest receipt of the held module tree.

    ``proven`` covers only the manifest read through the held entry guard
    before validation; no copy of the module is made.  It deliberately
    carries no pathname: a mutable namespace entry cannot remain
    identity-bound after its descriptor closes.
    """

    proven: bool
    reason: str = ""
    manifest: Optional[Dict[str, str]] = None

    def __bool__(self) -> bool:
        raise TypeError(
            "_ModuleBackupResult has no implicit truth value; inspect "
            ".proven and its captured manifest explicitly"
        )


class _FdBackupError(Exception):
    """Controlled fail-closed result for descriptor-relative backup work."""


class _ModuleFilesBusy(Exception):
    """A module file was held by another process; not a property of the module (#608)."""


_MODULE_FILES_BUSY_REASON = (
    "Module files were busy; publication stopped before registry access"
)


class _ModuleFilesRefused(Exception):
    """A candidate's own reset masters cannot be read for its conflict scan."""


class _ModuleCheckUnavailable(ValueError):
    """The safety check produced no verdict while building registry bytes."""


def _coerce_module_safety_result(result: Any) -> ModuleSafetyResult:
    """Normalize legacy/mock booleans without accepting arbitrary truthiness.

    Production validators return ``ModuleSafetyResult``.  Exact booleans remain
    supported for older internal callers and deterministic tests; any other
    value is treated as validator unavailability and therefore cannot commit.
    """

    if isinstance(result, ModuleSafetyResult):
        return result
    if result is True:
        return ModuleSafetyResult(
            ModuleSafetyStatus.SAFE,
            "Legacy validator returned an explicit safe result",
        )
    if result is False:
        return ModuleSafetyResult(
            ModuleSafetyStatus.UNSAFE,
            "Legacy validator returned an explicit rejection",
        )
    return ModuleSafetyResult(
        ModuleSafetyStatus.UNAVAILABLE,
        f"Validator returned unsupported result type {type(result).__name__}",
    )


def _location_prefix_to_index(prefix: str) -> int:
    """Inverse of module_generator.get_location_prefix's 0-indexed scheme:
    0->A .. 25->Z, 26->AA, 27->AB, ...

    Used by INT-H2 to find the next free location-prefix index from existing
    location IDs. Reads the FULL alpha prefix (1-2 letters), so 'AA01' maps to
    index 26 (not 0), preventing reuse of already-used two-letter prefixes.
    """
    prefix = (prefix or "").upper()
    if len(prefix) == 1:
        return ord(prefix[0]) - 65
    if len(prefix) == 2:
        return (ord(prefix[0]) - 65 + 1) * 26 + (ord(prefix[1]) - 65)
    return 26 * 26  # 3+ letters: jump well past the 2-letter range


def _location_index_to_prefix(index: int) -> str:
    """Return the deterministic inverse prefix used by module generation."""
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        raise ValueError("Location prefix index must be a non-negative integer")
    if index < 26:
        return chr(65 + index)
    if index < 702:
        return chr(65 + (index // 26) - 1) + chr(65 + (index % 26))
    raise ValueError("The supported location-prefix namespace is exhausted")


class ModuleStitcher:
    """Manages automatic module integration and organic world building"""
    
    def __init__(self):
        """Initialize module stitcher"""
        # Use absolute paths to ensure consistency regardless of working directory
        self.modules_dir = os.path.abspath("modules")
        self.root_dir = os.path.dirname(self.modules_dir)
        self.world_registry_file = os.path.join(self.modules_dir, "world_registry.json")
        self.party_tracker_file = os.path.join(self.root_dir, "party_tracker.json")

        # Ensure directories exist
        os.makedirs(self.modules_dir, exist_ok=True)

        # Load or create world registry
        self.world_registry = self._load_world_registry()
        # Modules the last scan could not join because their ids collide
        # with a registered module: [{"module", "collides_with",
        # "refused_because"}], and the unplayed ones it joined by
        # renumbering a copy: [{"module", "collides_with", "renumbered"}].
        # And the installed ones publication refused, or could not prove and
        # left unjoined: [{"module", "reason", "cause"}], where cause is a
        # NotJoinedCause value or None. A publication that could not be proven
        # is "unproven", or "registry_read_only" while the registry is
        # read-only.
        self.import_required = []
        self.imported = []
        self.not_joined = []
        
        # Clean up old connections if they exist (migration to isolated modules)
        if 'connections' in self.world_registry:
            print("Migrating to isolated module architecture - removing cross-module connections")
            del self.world_registry['connections']
            self.world_registry['isolatedModules'] = True
            # Redone in memory on every construction, so a read-only
            # registry costs nothing here (issue #654).
            safe_write_json(
                self.world_registry_file, self.world_registry, stop_if_read_only=True
            )
    
    def _default_world_registry(self) -> Dict[str, Any]:
        return {
            "worldName": "Fantasy Adventure World",
            "registryVersion": "1.0.0",
            "lastUpdated": datetime.now().isoformat(),
            "modules": {},
            "areas": {},
            "themes": {},
            "isolatedModules": True,
        }

    def _load_world_registry(self) -> Dict[str, Any]:
        """Load the world registry, tolerating a corrupt/unreadable file.

        Issue #173: the registry is ADVISORY metadata, not the source of truth for
        which modules exist. A corrupt world_registry.json used to make this raise,
        which crashed ModuleStitcher construction and therefore bricked the module
        scan/list (every module skipped -> "No modules available") even with real
        modules on disk. Now a corrupt file yields an in-memory default (the
        corrupt file is left ON DISK for forensics; the build/integration path
        rewrites a valid registry on its next success). Reads never brick.
        """
        if os.path.exists(self.world_registry_file):
            try:
                loaded = safe_json_load(self.world_registry_file)
            except Exception as exc:
                print(
                    "[MODULES] world_registry.json is unreadable "
                    f"({exc}); using default metadata. The file is left in place; "
                    "it will be rebuilt on the next successful module registration."
                )
                return self._default_world_registry()
            if isinstance(loaded, dict):
                return loaded
            print(
                "[MODULES] world_registry.json is not a JSON object; using "
                "default metadata (file left in place for inspection)."
            )
            return self._default_world_registry()
        default_registry = self._default_world_registry()
        safe_write_json(self.world_registry_file, default_registry)
        return default_registry

    def _target_module_path(self, module_name: str) -> Optional[str]:
        """Return the exact, contained module path or ``None`` if unsafe."""
        if not isinstance(module_name, str) or not module_name.strip():
            return None
        if (
            module_name != module_name.strip()
            or module_name in {".", ".."}
            or module_name.endswith(".")
            or any(ord(character) < 32 for character in module_name)
        ):
            return None
        if (
            os.path.isabs(module_name)
            or os.path.basename(module_name) != module_name
            or "/" in module_name
            or "\\" in module_name
            or module_name.startswith(".")
            or (os.name == "nt" and ":" in module_name)
        ):
            return None

        try:
            modules_root = os.path.realpath(self.modules_dir)
            module_path = os.path.join(self.modules_dir, module_name)
            resolved_module = os.path.realpath(module_path)
        except (OSError, ValueError):
            return None
        if os.path.dirname(resolved_module) != modules_root:
            return None
        return module_path

    @staticmethod
    def _is_symlink_or_reparse(path: str) -> bool:
        """Reject links and Windows reparse points at destructive boundaries."""
        try:
            path_stat = os.lstat(path)
        except OSError:
            return True
        reparse_flag = 0x0400  # Windows FILE_ATTRIBUTE_REPARSE_POINT
        return stat.S_ISLNK(path_stat.st_mode) or bool(
            getattr(path_stat, "st_file_attributes", 0) & reparse_flag
        )

    @staticmethod
    def _lstat_or_absent(path: str) -> Optional[os.stat_result]:
        """Return exact entry metadata; only FileNotFoundError means absent."""
        try:
            return os.lstat(path)
        except FileNotFoundError:
            return None

    def _exact_module_entry_state(
        self, module_name: str, module_path: str
    ) -> Tuple[str, Optional[os.stat_result], str]:
        """Classify one exact lexical module entry without following aliases."""
        try:
            with os.scandir(self.modules_dir) as entries:
                entry_names = [entry.name for entry in entries]
        except OSError:
            return "unsafe", None, "Modules directory could not be inspected"

        if any(
            self._module_names_alias(name, module_name) and name != module_name
            for name in entry_names
        ):
            return "unsafe", None, "A case-aliased module entry exists"
        if module_name not in entry_names:
            try:
                target_stat = self._lstat_or_absent(module_path)
            except (OSError, ValueError):
                return "unsafe", None, "Exact module absence could not be proven"
            if target_stat is not None:
                return "unsafe", None, "Exact module entry identity is ambiguous"
            return "absent", None, "Exact public module entry is absent"

        try:
            target_stat = self._lstat_or_absent(module_path)
        except (OSError, ValueError):
            return "unsafe", None, "Exact module entry could not be inspected"
        if target_stat is None:
            return "unsafe", None, "Exact module entry changed during inspection"
        if self._is_symlink_or_reparse(module_path):
            return "unsafe", None, "Exact module entry is a link or reparse point"
        try:
            if os.path.ismount(module_path):
                return "unsafe", None, "Exact module entry is a mount point"
        except OSError:
            return "unsafe", None, "Exact module mount state could not be proven"
        if not stat.S_ISDIR(target_stat.st_mode):
            return "unsafe", None, "Exact module entry is not a directory"
        return "directory", target_stat, ""

    def _exact_cleanup_target_state(
        self, module_name: str, module_path: str
    ) -> Tuple[str, Optional[os.stat_result], str]:
        """Compatibility seam for the proof-bound cleanup path."""
        return self._exact_module_entry_state(module_name, module_path)

    @staticmethod
    def _stable_directory_identity(
        path_stat: os.stat_result,
    ) -> Optional[Tuple[int, int, int]]:
        """Return a usable stable directory identity or fail closed."""
        mode = getattr(path_stat, "st_mode", None)
        device = getattr(path_stat, "st_dev", None)
        inode = getattr(path_stat, "st_ino", None)
        if (
            not isinstance(mode, int)
            or not stat.S_ISDIR(mode)
            or not isinstance(device, int)
            or not isinstance(inode, int)
            or inode == 0
        ):
            return None
        return device, inode, stat.S_IFMT(mode)

    def _revalidate_exact_module_entry_guard(
        self, guard: _ExactModuleEntryGuard
    ) -> Tuple[bool, str]:
        """Rebind a lexical path and held handle to the initial identity.

        This closes cooperative/manual swap windows at explicit publication
        boundaries. It does not claim atomic protection against a hostile actor
        swapping the path between a successful check and an individual legacy
        path-based filesystem operation.
        """
        state, current_stat, reason = self._exact_module_entry_state(
            guard.module_name, guard.module_path
        )
        if state != "directory" or current_stat is None:
            return False, reason or "Exact module entry is no longer a directory"
        try:
            held_stat = os.fstat(guard.descriptor)
        except (OSError, TypeError, ValueError):
            return False, "Held module directory identity could not be inspected"
        current_identity = self._stable_directory_identity(current_stat)
        held_identity = self._stable_directory_identity(held_stat)
        if (
            current_identity is None
            or held_identity is None
            or current_identity != guard.identity
            or held_identity != guard.identity
        ):
            return False, "Exact module directory identity changed"
        return True, ""

    def _acquire_exact_module_entry_guard(
        self,
        module_name: str,
        module_path: str,
        initial_stat: os.stat_result,
    ) -> Tuple[Optional[_ExactModuleEntryGuard], str]:
        """Hold a no-follow directory descriptor when the platform supports it."""
        identity = self._stable_directory_identity(initial_stat)
        windows = _windows_held_handles_supported()
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        if identity is None or not (windows or (nofollow and directory)):
            return None, "Stable no-follow directory identity is unsupported"

        descriptor = None
        try:
            if windows:
                descriptor = _open_windows_no_follow(module_path, directory=True)
            else:
                flags = os.O_RDONLY | nofollow | directory
                flags |= getattr(os, "O_CLOEXEC", 0)
                descriptor = os.open(module_path, flags)
            held_stat = os.fstat(descriptor)
            if self._stable_directory_identity(held_stat) != identity:
                return None, "Held module directory identity does not match"
            held_path = module_path
            if windows:
                # OPEN_REPARSE_POINT holds a link as itself; refusing it is
                # the O_NOFOLLOW proof. A volume with no serial cannot bind
                # the manifest's device checks, and one whose handle has no
                # final path (a network share) cannot name children through
                # the held directory (issue #608).
                if self._stat_result_is_reparse(held_stat):
                    return None, "Held module directory identity does not match"
                if held_stat.st_dev == 0:
                    return None, "Stable no-follow directory identity is unsupported"
                try:
                    held_path = _windows_final_path(descriptor)
                except OSError:
                    return None, "Stable no-follow directory identity is unsupported"
            guard = _ExactModuleEntryGuard(
                module_name,
                module_path,
                descriptor,
                identity,
                held_path,
            )
            valid, reason = self._revalidate_exact_module_entry_guard(guard)
            if not valid:
                return None, reason
            descriptor = None
            return guard, ""
        except (OSError, TypeError, ValueError):
            return None, "Stable no-follow directory identity could not be held"
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except (OSError, TypeError, ValueError):
                    pass

    @staticmethod
    def _close_exact_module_entry_guard(
        guard: Optional[_ExactModuleEntryGuard],
    ) -> None:
        if guard is None:
            return
        try:
            os.close(guard.descriptor)
        except (OSError, TypeError, ValueError):
            pass

    def _revalidate_publication_entry(
        self,
        module_name: str,
        module_path: str,
        initial_state: str,
        guard: Optional[_ExactModuleEntryGuard],
    ) -> Tuple[bool, str]:
        if initial_state == "directory":
            if guard is None:
                return False, "Stable module directory identity is unavailable"
            return self._revalidate_exact_module_entry_guard(guard)
        if initial_state == "absent":
            state, _path_stat, reason = self._exact_module_entry_state(
                module_name, module_path
            )
            if state == "absent":
                return True, ""
            return False, reason or "Exact module absence changed"
        return False, "Initial exact module entry state was not proven"

    def _publication_transactions_inactive_for_cleanup_locked(
        self,
    ) -> Tuple[bool, str]:
        """Temporary GAP-01 seam; Task 3 replaces it with journal recovery."""
        transaction_root = os.path.join(
            self.modules_dir, ".publication_transactions"
        )
        active_root = os.path.join(transaction_root, "active")

        try:
            transaction_stat = self._lstat_or_absent(transaction_root)
        except (OSError, ValueError):
            return False, "Publication transaction root could not be inspected"
        if transaction_stat is not None:
            if self._is_symlink_or_reparse(transaction_root):
                return False, "Publication transaction root is unsafe"
            try:
                if os.path.ismount(transaction_root):
                    return False, "Publication transaction root is a mount point"
                if not stat.S_ISDIR(transaction_stat.st_mode):
                    return False, "Publication transaction root is not a directory"
            except OSError:
                return False, "Publication transaction root could not be inspected"

        try:
            active_stat = self._lstat_or_absent(active_root)
        except (OSError, ValueError):
            return False, "Active publication state could not be inspected"
        if active_stat is None:
            return True, ""
        if self._is_symlink_or_reparse(active_root):
            return False, "Active publication state is unsafe"
        try:
            if os.path.ismount(active_root):
                return False, "Active publication state is a mount point"
            if not stat.S_ISDIR(active_stat.st_mode):
                return False, "Active publication state is not a directory"
            with os.scandir(active_root) as entries:
                if next(entries, None) is not None:
                    return False, "An active publication transaction remains"
        except OSError:
            return False, "Active publication state could not be inspected"
        return True, ""

    def _prepare_orphan_quarantine_root_locked(self) -> Tuple[Optional[str], str]:
        """Create or verify the contained same-filesystem quarantine root."""
        quarantine_root = os.path.join(
            self.modules_dir, ".module_orphan_quarantine"
        )
        try:
            with os.scandir(self.modules_dir) as entries:
                entry_names = [entry.name for entry in entries]
            quarantine_name = os.path.basename(quarantine_root)
            if any(
                self._module_names_alias(name, quarantine_name)
                and name != quarantine_name
                for name in entry_names
            ):
                return None, "A case-aliased quarantine root exists"
            quarantine_stat = self._lstat_or_absent(quarantine_root)
            if quarantine_stat is not None:
                if self._is_symlink_or_reparse(quarantine_root):
                    return None, "Orphan quarantine root is unsafe"
                if not stat.S_ISDIR(quarantine_stat.st_mode):
                    return None, "Orphan quarantine root is not a directory"
            else:
                os.mkdir(quarantine_root, 0o700)
                quarantine_stat = self._lstat_or_absent(quarantine_root)
                if quarantine_stat is None:
                    return None, "Orphan quarantine root creation is unproven"
                if not stat.S_ISDIR(quarantine_stat.st_mode):
                    return None, "Orphan quarantine root is not a directory"

            modules_root = os.path.realpath(self.modules_dir)
            resolved_quarantine = os.path.realpath(quarantine_root)
            if os.path.dirname(resolved_quarantine) != modules_root:
                return None, "Orphan quarantine root is not contained"
            if self._is_symlink_or_reparse(quarantine_root):
                return None, "Orphan quarantine root became unsafe"
            if os.path.ismount(quarantine_root):
                return None, "Orphan quarantine root is a mount point"
        except (OSError, ValueError):
            return None, "Orphan quarantine root could not be prepared"
        return quarantine_root, ""

    def _quarantined_tree_safe_to_purge(self, quarantine_path: str) -> bool:
        """Do not recursively purge a tree containing link/reparse/mount edges."""
        def raise_walk_error(walk_error):
            raise walk_error

        try:
            for directory, child_directories, child_files in os.walk(
                quarantine_path,
                topdown=True,
                onerror=raise_walk_error,
                followlinks=False,
            ):
                for child_name in child_directories + child_files:
                    child_path = os.path.join(directory, child_name)
                    if self._is_symlink_or_reparse(child_path):
                        return False
                    if os.path.isdir(child_path) and os.path.ismount(child_path):
                        return False
            return True
        except OSError:
            return False

    @staticmethod
    def _sync_directory_if_supported(directory: str) -> bool:
        """Synchronize directory-entry changes where the platform supports it."""
        if os.name == "nt":
            return True
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = None
        sync_ok = False
        close_ok = True
        unsupported = {
            errno.EINVAL,
            getattr(errno, "ENOTSUP", errno.EINVAL),
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
            getattr(errno, "ENOSYS", errno.EINVAL),
        }
        try:
            descriptor = os.open(directory, flags)
            try:
                os.fsync(descriptor)
                sync_ok = True
            except OSError as exc:
                sync_ok = exc.errno in unsupported
            except (TypeError, ValueError):
                sync_ok = False
        except (OSError, TypeError, ValueError):
            sync_ok = False
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except (OSError, TypeError, ValueError):
                    close_ok = False
        return sync_ok and close_ok

    def _read_registry_snapshot(self) -> Tuple[Optional[Dict[str, Any]], str]:
        """Fresh-read and shape-check the on-disk world registry."""
        try:
            with open(self.world_registry_file, "r", encoding="utf-8") as handle:
                registry = json.load(handle)
        except Exception as exc:
            return None, f"World registry could not be read: {exc}"

        if not isinstance(registry, dict):
            return None, "World registry is not a JSON object"
        if not isinstance(registry.get("modules"), dict):
            return None, "World registry 'modules' value is not an object"
        # Startup reconciliation writes a registry with no 'areas' key at
        # all; that is an empty area map, not a malformed one.
        if "areas" not in registry:
            registry["areas"] = {}
        if not isinstance(registry.get("areas"), dict):
            return None, "World registry 'areas' value is not an object"
        return registry, ""

    @staticmethod
    def _module_names_alias(first: Any, second: Any) -> bool:
        """Treat case aliases as identical only on case-insensitive platforms."""
        if not isinstance(first, str) or not isinstance(second, str):
            return False
        return first == second or (
            os.name == "nt" and first.casefold() == second.casefold()
        )

    @classmethod
    def _registry_references_module(
        cls, registry: Dict[str, Any], module_name: str
    ) -> bool:
        modules = registry.get("modules", {})
        if any(cls._module_names_alias(key, module_name) for key in modules):
            return True
        if any(
            isinstance(module_data, dict)
            and cls._module_names_alias(
                module_data.get("moduleName"), module_name
            )
            for module_data in modules.values()
        ):
            return True
        return any(
            isinstance(area_data, dict)
            and cls._module_names_alias(area_data.get("module"), module_name)
            for area_data in registry.get("areas", {}).values()
        )

    def _module_proven_unjoined(self, module_name: str) -> bool:
        """Installed, and the registry does not join it (issue #608).

        Absent or a bare stub counts as unjoined; any other row proves
        nothing, so it is False. When the file cannot be read, this session's
        registry decides: it is the world this session plays.
        """
        if not os.path.isdir(os.path.join(self.modules_dir, module_name)):
            return False
        registry, _reason = self._read_registry_snapshot()
        if registry is None:
            registry = self.world_registry
        if not isinstance(registry, dict):
            return False
        return not self._registry_references_module(
            registry, module_name
        ) or self._is_registry_stub(registry, module_name)

    @classmethod
    def _is_registry_stub(
        cls, registry: Dict[str, Any], module_name: str
    ) -> bool:
        """Whether the registry names the module only by a bare stub.

        Startup reconciliation records every module directory as exactly
        ``{"moduleName": M}``. Such an entry carries no areas and no module
        data, so the module has not been integrated yet. Any other field,
        an alias entry, or an area row naming the module means it is not a
        stub.
        """
        modules = registry.get("modules", {})
        areas = registry.get("areas", {})
        if not isinstance(modules, dict) or not isinstance(areas, dict):
            return False
        if modules.get(module_name) != {"moduleName": module_name}:
            return False
        for key, module_data in modules.items():
            if key == module_name:
                continue
            if cls._module_names_alias(key, module_name):
                return False
            if isinstance(module_data, dict) and cls._module_names_alias(
                module_data.get("moduleName"), module_name
            ):
                return False
        return not any(
            isinstance(area_data, dict)
            and cls._module_names_alias(area_data.get("module"), module_name)
            for area_data in areas.values()
        )

    def _prove_module_absent_from_registry_locked(
        self, module_name: str
    ) -> RegistryAbsenceResult:
        registry, reason = self._read_registry_snapshot()
        if registry is None:
            return RegistryAbsenceResult(module_name, False, False, reason)
        absent = not self._registry_references_module(registry, module_name)
        return RegistryAbsenceResult(
            module_name,
            True,
            absent,
            "No exact registry reference exists"
            if absent
            else "The exact module is still referenced by the registry",
        )

    def prove_module_absent_from_registry_locked(
        self, module_name: str
    ) -> RegistryAbsenceResult:
        """Fresh proof API for callers that already own module_refresh_lock."""
        if self._target_module_path(module_name) is None:
            return RegistryAbsenceResult(
                module_name,
                False,
                False,
                "Invalid or non-contained module name",
            )
        from utils.module_refresh_lock import assert_module_refresh_lock_owned

        assert_module_refresh_lock_owned()
        return self._prove_module_absent_from_registry_locked(module_name)

    def cleanup_unpublished_module_locked(
        self,
        expected_module_name: str,
        publication_result: TargetedPublicationResult,
        fresh_absence_result: RegistryAbsenceResult,
    ) -> OrphanCleanupResult:
        """Quarantine one exact unpublished module after complete fresh proof.

        The caller must still own ``module_refresh_lock``.  No boolean can grant
        authority: both proof-bearing result objects and their exact identities
        are revalidated here immediately before the destructive rename.
        """

        def recovery(reason: str, quarantine_path: Optional[str] = None):
            return OrphanCleanupResult(
                OrphanCleanupStatus.RECOVERY_REQUIRED,
                expected_module_name
                if isinstance(expected_module_name, str)
                else "unknown",
                reason,
                quarantine_path,
            )

        if self._target_module_path(expected_module_name) is None:
            return recovery("Expected module name is invalid or not contained")
        from utils.module_refresh_lock import assert_module_refresh_lock_owned

        assert_module_refresh_lock_owned()

        if type(publication_result) is not TargetedPublicationResult:
            return recovery("Publication proof object is unavailable")
        if type(fresh_absence_result) is not RegistryAbsenceResult:
            return recovery("Fresh registry-absence proof object is unavailable")
        if publication_result.cleanup_safe_for(expected_module_name) is not True:
            return recovery("Publication rollback proof is incomplete or mismatched")
        if (
            fresh_absence_result.module_name != expected_module_name
            or fresh_absence_result.cleanup_safe is not True
        ):
            return recovery("Fresh registry-absence proof is incomplete or mismatched")

        module_path = self._target_module_path(expected_module_name)
        if module_path is None:
            return recovery("Expected module name is invalid or not contained")

        transactions_inactive, transaction_reason = (
            self._publication_transactions_inactive_for_cleanup_locked()
        )
        if not transactions_inactive:
            return recovery(transaction_reason)

        target_state, target_stat, target_reason = (
            self._exact_cleanup_target_state(expected_module_name, module_path)
        )
        if target_state == "absent":
            return OrphanCleanupResult(
                OrphanCleanupStatus.ALREADY_ABSENT,
                expected_module_name,
                target_reason,
            )
        if target_state != "directory" or target_stat is None:
            return recovery(target_reason)

        quarantine_root, quarantine_reason = (
            self._prepare_orphan_quarantine_root_locked()
        )
        if quarantine_root is None:
            return recovery(quarantine_reason)

        quarantine_path = None
        for _ in range(8):
            candidate = os.path.join(quarantine_root, uuid4().hex)
            try:
                candidate_stat = self._lstat_or_absent(candidate)
            except (OSError, ValueError):
                return recovery("Opaque quarantine path could not be inspected")
            if candidate_stat is None:
                quarantine_path = candidate
                break
        if quarantine_path is None:
            return recovery("A unique opaque quarantine path could not be allocated")

        try:
            resolved_quarantine = os.path.realpath(quarantine_path)
            if os.path.dirname(resolved_quarantine) != os.path.realpath(
                quarantine_root
            ):
                return recovery("Opaque quarantine path is not contained")
            os.replace(module_path, quarantine_path)
        except (OSError, ValueError):
            return recovery("Exact module could not be quarantined")

        try:
            public_stat = self._lstat_or_absent(module_path)
            quarantine_stat = self._lstat_or_absent(quarantine_path)
            if quarantine_stat is None:
                quarantine_valid = False
            else:
                same_device = quarantine_stat.st_dev == target_stat.st_dev
                same_inode = (
                    not target_stat.st_ino
                    or not quarantine_stat.st_ino
                    or quarantine_stat.st_ino == target_stat.st_ino
                )
                quarantine_valid = (
                    public_stat is None
                    and same_device
                    and same_inode
                    and stat.S_ISDIR(quarantine_stat.st_mode)
                    and not self._is_symlink_or_reparse(quarantine_path)
                )
        except (OSError, ValueError):
            quarantine_valid = False
        if not quarantine_valid:
            return recovery(
                "Quarantine rename could not be verified", quarantine_path
            )

        quarantine_synced = self._sync_directory_if_supported(quarantine_root)
        modules_synced = self._sync_directory_if_supported(self.modules_dir)
        if not quarantine_synced or not modules_synced:
            return recovery(
                "Quarantine rename could not be fully synchronized",
                quarantine_path,
            )

        if self._quarantined_tree_safe_to_purge(quarantine_path):
            try:
                shutil.rmtree(quarantine_path)
            except Exception:
                # The public name is durably absent. Hidden evidence is
                # deliberately retained for a later maintenance/recovery pass.
                pass

        return OrphanCleanupResult(
            OrphanCleanupStatus.REMOVED,
            expected_module_name,
            "Exact public module entry was quarantined",
            quarantine_path,
        )

    def prove_module_absent_from_registry(
        self, module_name: str
    ) -> RegistryAbsenceResult:
        """Prove from a fresh disk read whether exact-module cleanup is safe."""
        from utils.module_refresh_lock import module_refresh_lock

        if self._target_module_path(module_name) is None:
            return RegistryAbsenceResult(
                module_name,
                False,
                False,
                "Invalid or non-contained module name",
            )
        with module_refresh_lock() as acquired:
            if not acquired:
                return RegistryAbsenceResult(
                    module_name,
                    False,
                    False,
                    "Module publication lock timed out",
                )
            return self.prove_module_absent_from_registry_locked(module_name)

    def _registry_matches_snapshot(
        self, expected: Dict[str, Any]
    ) -> Tuple[bool, str]:
        registry, reason = self._read_registry_snapshot()
        if registry is None:
            return False, reason
        if registry != expected:
            return False, "World registry readback did not match the expected snapshot"
        return True, ""

    def _restore_registry_snapshot(
        self, prior_registry: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Atomically restore and fresh-read the prior registry snapshot."""
        try:
            write_result = safe_write_json(
                self.world_registry_file, deepcopy(prior_registry),
                stop_if_read_only=True,
            )
        except Exception as exc:
            return False, f"Prior registry restore raised: {exc}"
        if write_result is not True:
            return False, "Prior registry restore did not report success"

        restored, reason = self._read_registry_snapshot()
        if restored is None:
            return False, f"Prior registry restore could not be verified: {reason}"
        if restored != prior_registry:
            return False, "Prior registry restore readback did not match"

        # The in-memory view changes only after a matching disk read proves it.
        self.world_registry = deepcopy(restored)
        return True, ""

    def _validate_required_publication_files(
        self, module_path: str
    ) -> Tuple[bool, str]:
        """Validate every publication-critical JSON object and area schema."""
        schema_dir = Path(__file__).resolve().parents[2] / "schemas"
        required_files = {
            "module_plot.json": "plot_schema.json",
            "module_context.json": None,
        }
        # The module builder writes a module-level party tracker; published
        # modules (the repo's own, and modules dropped into modules/) never
        # ship one, and no play path reads it through the schema (the
        # declared start reads only its weather and politicalClimate). It is
        # checked only when present, and its content never refuses
        # publication (#586): a failure is logged and the module publishes.
        optional_files = {
            "party_tracker.json": "party_schema.json",
        }

        try:
            from jsonschema import Draft7Validator

            def load_object(path: Path) -> Dict[str, Any]:
                with path.open("r", encoding="utf-8") as handle:
                    value = json.load(handle)
                if not isinstance(value, dict):
                    raise ValueError(f"{path.name} is not a JSON object")
                return value

            def validate_available_schema(
                data: Dict[str, Any], schema_name: Optional[str], label: str
            ) -> None:
                if not schema_name:
                    return
                schema_path = schema_dir / schema_name
                if not schema_path.exists():
                    return
                schema = load_object(schema_path)
                Draft7Validator.check_schema(schema)
                errors = sorted(
                    Draft7Validator(schema).iter_errors(data),
                    key=lambda item: list(item.path),
                )
                if errors:
                    path = ".".join(str(part) for part in errors[0].path)
                    location = path or "root"
                    raise ValueError(
                        f"{label} failed {schema_name} at {location}: "
                        f"{errors[0].message}"
                    )

            module_root = Path(module_path)
            for filename, schema_name in required_files.items():
                file_path = module_root / filename
                if not file_path.is_file():
                    return False, f"Required publication file is missing: {filename}"
                data = load_object(file_path)
                validate_available_schema(data, schema_name, filename)
            for filename, schema_name in optional_files.items():
                file_path = module_root / filename
                if not os.path.lexists(file_path):
                    continue
                if not file_path.is_file():
                    return False, f"Publication file is not a regular file: {filename}"
                try:
                    data = load_object(file_path)
                    validate_available_schema(data, schema_name, filename)
                except (OSError, ValueError) as exc:
                    # Publication checks a module several times; report once.
                    warned = self.__dict__.setdefault("_own_tracker_warned", set())
                    if str(file_path) not in warned:
                        warned.add(str(file_path))
                        warning(
                            f"MODULE_PUBLICATION: {module_root.name}'s own {filename} "
                            f"is not used by play and fails: {exc}; publishing anyway",
                            category="module_integration",
                        )

            areas_dir = module_root / "areas"
            if not areas_dir.is_dir():
                return False, "Required areas directory is missing"
            area_files = sorted(
                path
                for path in areas_dir.glob("*.json")
                if not path.name.endswith("_BU.json")
            )
            if not area_files:
                return False, "No publishable area JSON files were found"

            seen_area_ids = set()
            for area_file in area_files:
                area = load_object(area_file)
                validate_available_schema(
                    area,
                    "locationfile_schema.json",
                    f"areas/{area_file.name}",
                )
                area_id = area.get("areaId")
                if not isinstance(area_id, str) or not area_id:
                    return False, f"areas/{area_file.name} has no string areaId"
                if area_file.stem != area_id:
                    return False, (
                        f"areas/{area_file.name} does not match areaId {area_id}"
                    )
                if area_id in seen_area_ids:
                    return False, f"Duplicate areaId in module: {area_id}"
                seen_area_ids.add(area_id)

            return True, ""
        except Exception as exc:
            return False, f"Publication file validation failed: {exc}"

    def _module_identity_sets_for_conflict_scan(
        self, module_path: str
    ) -> Tuple[Optional[set], Optional[set], str]:
        """Read area/location identifiers without changing a module tree."""
        areas_path = os.path.join(module_path, "areas")
        try:
            if self._is_symlink_or_reparse(module_path):
                return None, None, "Module path is a link or reparse point"
            if not os.path.isdir(areas_path) or self._is_symlink_or_reparse(
                areas_path
            ):
                return None, None, "Module areas directory is unavailable or unsafe"

            area_ids = set()
            location_ids = set()
            with os.scandir(areas_path) as entries:
                for entry in sorted(entries, key=lambda item: item.name):
                    if not entry.name.endswith(".json") or entry.name.endswith(
                        "_BU.json"
                    ):
                        continue
                    if entry.is_symlink() or not entry.is_file(
                        follow_symlinks=False
                    ):
                        return None, None, "Module area entry is unsafe"
                    area_data = safe_json_load(entry.path)
                    if not isinstance(area_data, dict):
                        return None, None, "Module area JSON is unreadable"
                    area_id = area_data.get("areaId")
                    if not isinstance(area_id, str) or not area_id.strip():
                        return None, None, "Module areaId is unavailable"
                    if area_id in area_ids:
                        return None, None, "Module contains duplicate area IDs"
                    area_ids.add(area_id)
                    locations = area_data.get("locations", [])
                    if not isinstance(locations, (list, dict)):
                        return None, None, "Module locations are malformed"
                    values = locations.values() if isinstance(locations, dict) else locations
                    for location in values:
                        if not isinstance(location, dict):
                            continue
                        location_id = location.get("locationId")
                        if isinstance(location_id, str) and location_id.strip():
                            if location_id in location_ids:
                                return None, None, (
                                    "Module contains duplicate location IDs"
                                )
                            location_ids.add(location_id)
            if not area_ids:
                return None, None, "Module has no area identifiers"
            return area_ids, location_ids, ""
        except (OSError, ValueError) as exc:
            return None, None, f"Module identifiers could not be inspected: {exc}"

    @staticmethod
    def _read_error_is_busy(exc: OSError, path: str) -> bool:
        """Whether a failed file read means another process holds the file.

        The C runtime reports a Windows sharing or lock violation as access
        denied. So a denied read is classified by one Win32 read of the same
        file, whose bytes are not used: busy unless that read also fails for
        a reason that is not transient (issue #608).
        """
        if is_transient_filesystem_error(exc):
            return True
        if not isinstance(exc, PermissionError):
            return False
        try:
            read_bytes_preserving_errors(path)
        except OSError as probe_exc:
            return is_transient_filesystem_error(probe_exc)
        return True

    def _paired_master_location_ids(self, module_path: str) -> set:
        """Read location ids from the candidate's paired ``_BU.json`` masters.

        A master repeats its live twin's areaId, so it cannot join the scan
        helper above. Only masters with a live twin are read: the managed
        import's BU refresh rewrites exactly those, and boot hydration turns
        an orphan into a live file before the refresh. A master the ID fixer
        could not have read raises ``_ModuleFilesRefused`` so the module is
        refused with a report rather than skipped in silence (issue #609). A
        master busy in another process raises ``_ModuleFilesBusy`` (#608).
        """
        areas_path = os.path.join(module_path, "areas")
        location_ids = set()
        try:
            with os.scandir(areas_path) as entries:
                by_name = {entry.name: entry for entry in entries}
            for name in sorted(by_name):
                if not name.endswith("_BU.json"):
                    continue
                if name[: -len("_BU.json")] + ".json" not in by_name:
                    continue
                entry = by_name[name]
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    raise _ModuleFilesRefused(
                        f"Paired master is not a regular file: areas/{name}"
                    )
                try:
                    master = safe_json_load(entry.path)
                except OSError as exc:
                    if self._read_error_is_busy(exc, entry.path):
                        raise _ModuleFilesBusy(str(exc)) from exc
                    raise
                if not master:
                    continue
                if not isinstance(master, dict):
                    raise _ModuleFilesRefused(
                        f"Paired master is not a JSON object: areas/{name}"
                    )
                locations = master.get("locations", [])
                if isinstance(locations, (list, dict, str)) and not locations:
                    continue
                if not isinstance(locations, list):
                    raise _ModuleFilesRefused(
                        f"Paired master locations are malformed: areas/{name}"
                    )
                for location in locations:
                    if not isinstance(location, dict):
                        raise _ModuleFilesRefused(
                            f"Paired master location is malformed: areas/{name}"
                        )
                    location_id = location.get("locationId")
                    if not location_id:
                        continue
                    if isinstance(location_id, (list, dict)):
                        raise _ModuleFilesRefused(
                            f"Paired master locationId is malformed: areas/{name}"
                        )
                    if isinstance(location_id, str):
                        location_ids.add(location_id)
        except _ModuleFilesRefused:
            raise
        except (OSError, ValueError, UnicodeError, TypeError) as exc:
            if is_transient_filesystem_error(exc):
                raise _ModuleFilesBusy(str(exc)) from exc
            raise _ModuleFilesRefused(
                f"Paired masters could not be read: {exc}"
            ) from exc
        return location_ids

    def _detect_legacy_publication_conflicts(
        self,
        module_name: str,
        module_path: str,
        registry_snapshot: Dict[str, Any],
    ) -> Tuple[Optional[bool], str, Tuple[str, ...]]:
        """Detect whether a candidate's ids collide with registered modules.

        ``True`` means a managed import is required, ``False`` means registry-only
        publication can continue, and ``None`` means the read was unsafe or
        ambiguous. The third value names the registered modules whose ids
        collide (empty unless ``True``). The candidate's location ids include
        its paired ``_BU.json`` masters; a master that cannot be read raises
        ``_ModuleFilesRefused``. This helper never writes.
        """
        candidate_areas, candidate_locations, reason = (
            self._module_identity_sets_for_conflict_scan(module_path)
        )
        if candidate_areas is None or candidate_locations is None:
            return None, reason, ()

        registered_area_rows = registry_snapshot.get("areas", {})
        area_conflicts = candidate_areas.intersection(registered_area_rows)
        if area_conflicts:
            return True, (
                "Managed import is required for conflicting area IDs: "
                + ", ".join(sorted(area_conflicts))
            ), tuple(sorted({
                registered_area_rows[area_id].get("module")
                for area_id in area_conflicts
                if isinstance(registered_area_rows[area_id], dict)
                and isinstance(registered_area_rows[area_id].get("module"), str)
            }))

        # Issue #609: a reset master's ids are the module's ids too. Counting
        # them here sends a master-only collision to the managed import
        # instead of passing it as conflict-free.
        candidate_locations = candidate_locations | (
            self._paired_master_location_ids(module_path)
        )

        existing_location_ids = set()
        colliding_modules = set()
        existing_module_names = {
            area_data.get("module")
            for area_data in registry_snapshot.get("areas", {}).values()
            if isinstance(area_data, dict)
            and isinstance(area_data.get("module"), str)
            and area_data.get("module") != module_name
        }
        for existing_name in sorted(existing_module_names):
            existing_path = self._target_module_path(existing_name)
            if existing_path is None:
                return None, "Registered module path is unsafe", ()
            state, _entry_stat, state_reason = self._exact_module_entry_state(
                existing_name, existing_path
            )
            # Preserve compatibility with registries whose old module package
            # is no longer installed. There is no live tree to rewrite or
            # inspect in that case.
            if state == "absent":
                continue
            if state != "directory":
                return (
                    None,
                    f"Registered module path is unsafe: {state_reason}",
                    (),
                )
            _areas, locations, existing_reason = (
                self._module_identity_sets_for_conflict_scan(existing_path)
            )
            if locations is None:
                return None, existing_reason, ()
            existing_location_ids.update(locations)
            if candidate_locations.intersection(locations):
                colliding_modules.add(existing_name)

        location_conflicts = candidate_locations.intersection(
            existing_location_ids
        )
        if location_conflicts:
            return True, (
                "Managed import is required for conflicting location IDs: "
                + ", ".join(sorted(location_conflicts))
            ), tuple(sorted(colliding_modules))
        return False, "", ()
    
    def detect_new_modules(self) -> List[str]:
        """Detect new modules in the modules directory"""
        try:
            detected_modules = []
            
            if not os.path.exists(self.modules_dir):
                return detected_modules
            
            # Scan for module directories
            for item in os.listdir(self.modules_dir):
                item_path = os.path.join(self.modules_dir, item)
                
                # Skip files and hidden directories
                if not os.path.isdir(item_path) or item.startswith('.'):
                    continue
                    
                # Skip system directories
                if item in ['campaign_archives', 'campaign_summaries']:
                    continue

                # A failed rollback deliberately marks the exact module as
                # unusable. Never let a later broad scan publish it.
                if os.path.exists(os.path.join(item_path, ".corrupted")):
                    continue
                
                # Check if module has area files (current data structure)
                if self._has_area_files(item_path):
                    # Check if already registered (a bare stub is not)
                    if item not in self.world_registry.get(
                        'modules', {}
                    ) or self._is_registry_stub(self.world_registry, item):
                        detected_modules.append(item)
                        print(f"Detected new module: {item}")
            
            # Directory listing order is filesystem-dependent; integration
            # order decides which of two colliding modules is joined.
            return sorted(detected_modules)
            
        except Exception as e:
            print(f"Error detecting modules: {e}")
            return []
    
    def _has_area_files(self, module_path: str) -> bool:
        """Check if module directory contains area files (current structure)"""
        try:
            # Look for area files in areas/ subdirectory
            areas_folder = os.path.join(module_path, "areas")
            if not os.path.exists(areas_folder):
                return False
            
            pattern = os.path.join(areas_folder, "*.json")
            json_files = glob.glob(pattern)
            
            area_files = []
            for file_path in json_files:
                filename = os.path.basename(file_path)
                
                # Skip system files and backup files
                if (filename.startswith('module_') or 
                    filename.startswith('party_') or
                    filename.startswith('campaign_') or
                    filename.startswith('map_') or
                    filename.startswith('plot_') or
                    filename.endswith('_BU.json')):
                    continue
                
                # Check if it's an area file by loading and checking structure
                try:
                    data = safe_json_load(file_path)
                    if (data and 'areaId' in data and 'areaName' in data and
                        'locations' in data):
                        area_files.append(filename)
                except Exception as e:
                    warning(f"Skipped malformed area file {file_path}: {e}", category="module_integration")
                    continue
            
            return len(area_files) > 0
            
        except Exception as e:
            print(f"Error checking area files in {module_path}: {e}")
            return False
    
    def analyze_module(
        self, module_name: str, include_travel_narration: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Analyze module data, optionally performing the T032 creative call."""
        return self._analyze_module_path(
            os.path.join(self.modules_dir, module_name),
            module_name,
            include_travel_narration=include_travel_narration,
        )

    def _analyze_module_path(
        self,
        module_path: str,
        module_name: str,
        *,
        include_travel_narration: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Analyze one explicitly owned module tree, including hidden builds."""
        try:
            if not os.path.exists(module_path):
                return None
            
            module_data = {
                "moduleName": module_name,
                "areas": {},
                "themes": [],
                "plotObjective": "",
                "levelRange": {"min": 1, "max": 1},
                "connections": {}
            }
            
            # Extract area data from area files
            areas_data = self._extract_areas_data(module_path)
            if areas_data:
                module_data["areas"] = areas_data
                
                # Calculate level range from actual area data
                levels = []
                for area_data in areas_data.values():
                    if 'recommendedLevel' in area_data:
                        levels.append(area_data['recommendedLevel'])
                
                if levels:
                    module_data["levelRange"] = {
                        "min": min(levels),
                        "max": max(levels)
                    }
            
            # Extract plot themes and objectives
            plot_data = self._extract_plot_data(module_path)
            if plot_data:
                module_data["themes"] = plot_data.get("themes", [])
                module_data["plotObjective"] = plot_data.get("objective", "")
                # Override with plot level range if provided, otherwise keep calculated range
                if "levelRange" in plot_data:
                    module_data["levelRange"] = plot_data["levelRange"]
            
            if include_travel_narration:
                module_data["travelNarration"] = self._generate_travel_narration(
                    module_data
                )
            
            return module_data
            
        except Exception as e:
            print(f"Error analyzing module {module_name}: {e}")
            return None
    
    def _extract_areas_data(self, module_path: str) -> Dict[str, Any]:
        """Extract area data from area files in module"""
        areas_data = {}
        
        try:
            # Find all area files in the areas/ subdirectory
            areas_folder = os.path.join(module_path, "areas")
            if not os.path.exists(areas_folder):
                print(f"Warning: No areas/ folder found in {module_path}")
                return {}
            
            pattern = os.path.join(areas_folder, "*.json")
            json_files = glob.glob(pattern)
            
            for file_path in json_files:
                filename = os.path.basename(file_path)
                
                # Skip system files and backup files
                if (filename.startswith('module_') or 
                    filename.startswith('party_') or
                    filename.startswith('campaign_') or
                    filename.startswith('map_') or
                    filename.startswith('plot_') or
                    filename.endswith('_BU.json')):
                    continue
                
                try:
                    data = safe_json_load(file_path)
                    if (data and 'areaId' in data and 'areaName' in data):
                        area_id = data['areaId']
                        areas_data[area_id] = {
                            "areaName": data.get('areaName', ''),
                            "areaDescription": data.get('areaDescription', ''),
                            "areaType": data.get('areaType', ''),
                            "dangerLevel": data.get('dangerLevel', 'unknown'),
                            "recommendedLevel": data.get('recommendedLevel', 1),
                            "climate": data.get('climate', ''),
                            "terrain": data.get('terrain', ''),
                            "areaConnectivity": data.get('areaConnectivity', []),
                            "areaConnectivityId": data.get('areaConnectivityId', []),
                            "locationCount": len(data.get('locations', []))
                        }
                except Exception as e:
                    print(f"Error processing area file {file_path}: {e}")
                    continue
            
            return areas_data
            
        except Exception as e:
            print(f"Error extracting areas data from {module_path}: {e}")
            return {}
    
    def _extract_plot_data(self, module_path: str) -> Optional[Dict[str, Any]]:
        """Extract plot themes and objectives from module_plot.json"""
        try:
            plot_file = os.path.join(module_path, "module_plot.json")
            if not os.path.exists(plot_file):
                return None
            
            plot_data = safe_json_load(plot_file)
            if not plot_data:
                return None
            
            # Extract key information
            extracted = {
                "objective": plot_data.get('mainObjective', ''),
                "plotTitle": plot_data.get('plotTitle', ''),
                "themes": []
            }
            
            # Analyze plot points for themes
            plot_points = plot_data.get('plotPoints', [])
            
            for point in plot_points:
                # Extract themes from descriptions
                description = point.get('description', '')
                if description:
                    extracted["themes"].append(description)  # Full description for analysis
            
            # Level range should be calculated from actual area data, not from plot points
            # This function no longer sets levelRange - it's calculated from areas in analyze_module()
            
            return extracted
            
        except Exception as e:
            print(f"Error extracting plot data from {module_path}: {e}")
            return None
    
    def _generate_travel_narration(self, module_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI travel narration for transitioning to this module"""
        try:
            # Generate travel narration for this module
            system_prompt = """You are a fantasy adventure narrator. Generate brief, atmospheric travel narration for when a party transitions to a new adventure module. This should be 2-3 sentences that:

1. Describe the journey/travel to the new region
2. Set the mood and atmosphere for the new adventure
3. Provide DM guidance for presenting the transition
4. Keep it generic enough to work from any previous location

Examples:
- "The party travels for several days through winding country roads, eventually reaching the mist-shrouded village of..."
- "Word of strange happenings draws the adventurers northward, where rumors speak of..."
- "Following ancient trade routes, the party arrives at a region where..."

Use only standard ASCII characters in all text -- no smart quotes, no em-dashes, no Unicode. Use straight quotes and regular dashes only.

Return JSON with:
{
  "travelNarration": "atmospheric description for players",
  "dmGuidance": "instructions for DM on presenting the transition"
}"""
            
            # Prepare module data for narration
            module_name = module_data.get('moduleName', '')
            plot_objective = module_data.get('plotObjective', '')
            level_range = module_data.get('levelRange', {})
            
            # Get first area for setting context
            first_area_name = ""
            first_area_type = ""
            if module_data.get('areas'):
                first_area = list(module_data['areas'].values())[0]
                first_area_name = first_area.get('areaName', '')
                first_area_type = first_area.get('areaType', '')
            
            user_prompt = f"""Generate travel narration for transitioning to this module:

MODULE: {module_name}
OBJECTIVE: {plot_objective}
LEVEL RANGE: {level_range.get('min', 1)}-{level_range.get('max', 5)}
FIRST AREA: {first_area_name} ({first_area_type})

Create atmospheric travel narration that leads into this adventure."""
            
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                summ_config = config.DM_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_config = config.DM_SUMM_LMSTUDIO
            else:  # legacy
                summ_config = config.DM_SUMM_LEGACY

            response = capture_and_fanout("T032", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=summ_config["model"],
                temperature=0.8,
                **{k: v for k, v in summ_config.items() if k != "model"})

            # Parse AI response
            ai_response = response.choices[0].message.content
            try:
                narration_data = json.loads(ai_response)
                if (
                    not isinstance(narration_data, dict)
                    or set(narration_data) != {"travelNarration", "dmGuidance"}
                    or not all(
                        isinstance(narration_data[field], str)
                        and narration_data[field].strip()
                        for field in ("travelNarration", "dmGuidance")
                    )
                ):
                    raise ValueError(
                        "T032 requires exactly two useful narration fields"
                    )
                return {
                    "travelNarration": narration_data['travelNarration'].strip(),
                    "dmGuidance": narration_data['dmGuidance'].strip(),
                    "generatedDate": datetime.now().isoformat()
                }
            except (json.JSONDecodeError, TypeError, ValueError):
                print(f"Warning: Could not parse AI travel narration: {ai_response[:200]}...")
                return {
                    "travelNarration": f"The party travels to the {first_area_name} region, where new adventures await.",
                    "dmGuidance": "Present this as a clean transition to the new module.",
                    "generatedDate": datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"Error generating travel narration: {e}")
            return {
                "travelNarration": "The party travels to a new region where fresh adventures await.",
                "dmGuidance": "Present this as a transition to the new module.",
                "generatedDate": datetime.now().isoformat()
            }
    
    @staticmethod
    def _stat_result_is_reparse(path_stat: os.stat_result) -> bool:
        attributes = getattr(path_stat, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(reparse_flag and attributes & reparse_flag)

    @staticmethod
    def _filesystem_entry_identity(
        path_stat: os.stat_result,
    ) -> Optional[Tuple[int, int, int]]:
        mode = getattr(path_stat, "st_mode", None)
        device = getattr(path_stat, "st_dev", None)
        inode = getattr(path_stat, "st_ino", None)
        if (
            not isinstance(mode, int)
            or not isinstance(device, int)
            or not isinstance(inode, int)
            or inode == 0
        ):
            return None
        return device, inode, stat.S_IFMT(mode)

    @staticmethod
    def _descriptor_mount_id(descriptor: int) -> Optional[int]:
        """Read the mount identity for one already-open descriptor.

        Linux: the mnt_id from /proc/self/fdinfo. Native Windows has no mount
        id: another volume is reachable inside a tree only through a reparse
        point, which every level refuses, so that refusal is the proof and
        the volume serial stands in for the id (issue #608).
        """
        if os.name == "nt":
            try:
                device = os.fstat(int(descriptor)).st_dev
            except (OSError, TypeError, ValueError):
                return None
            return device if isinstance(device, int) and device > 0 else None
        try:
            with open(
                f"/proc/self/fdinfo/{int(descriptor)}",
                "r",
                encoding="ascii",
            ) as descriptor_info:
                for line in descriptor_info:
                    if line.startswith("mnt_id:"):
                        value = int(line.split(":", 1)[1].strip())
                        return value if value > 0 else None
        except (OSError, TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _fd_relative_backup_supported() -> bool:
        if os.name == "nt":
            # The receipt is taken through held handles (issue #608).
            return _windows_held_handles_supported()
        return (
            os.name != "nt"
            and bool(getattr(os, "O_NOFOLLOW", 0))
            and bool(getattr(os, "O_DIRECTORY", 0))
            and bool(getattr(os, "O_PATH", 0))
            and _OPEN_SUPPORTS_DIR_FD
            and _MKDIR_SUPPORTS_DIR_FD
            and _STAT_SUPPORTS_DIR_FD
            and _STAT_SUPPORTS_NOFOLLOW
            and _LISTDIR_SUPPORTS_FD
            and os.path.isdir("/proc/self/fd")
            and os.path.isdir("/proc/self/fdinfo")
            and callable(getattr(os, "read", None))
            and callable(getattr(os, "write", None))
            and callable(getattr(os, "fsync", None))
        )

    @staticmethod
    def _close_backup_descriptor(descriptor: int) -> bool:
        try:
            os.close(descriptor)
            return True
        except (OSError, TypeError, ValueError):
            return False

    @staticmethod
    def _held_entry_stat(
        parent_descriptor: int, parent_path: Optional[str], name: str
    ) -> os.stat_result:
        """Stat one child of a held directory without following a link.

        Native Windows has no dir_fd. The child is named through the held
        parent's final path (_windows_final_path): every component is a real
        directory the held handles pin, and no name is rewritten (issue #608).
        """
        if os.name == "nt":
            return os.lstat(os.path.join(parent_path, name))
        return os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)

    def _fd_directory_names(
        self, directory_descriptor: int, held_path: Optional[str]
    ) -> List[str]:
        """Return a deterministic entry list using a fresh directory offset."""
        scan_descriptor = None
        close_ok = True
        try:
            if os.name == "nt":
                # List the held directory by its final path and bind that
                # path to the held handle on both sides (issue #608).
                held_identity = self._filesystem_entry_identity(
                    os.fstat(directory_descriptor)
                )
                before = self._filesystem_entry_identity(os.lstat(held_path))
                names = os.listdir(held_path)
                after = self._filesystem_entry_identity(os.lstat(held_path))
                if held_identity is None or not (
                    before == held_identity == after
                ):
                    raise _FdBackupError(
                        "Directory enumeration could not be proven"
                    )
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                flags |= getattr(os, "O_CLOEXEC", 0)
                scan_descriptor = os.open(
                    ".", flags, dir_fd=directory_descriptor
                )
                names = os.listdir(scan_descriptor)
            if not all(
                isinstance(name, str)
                and name not in {"", ".", ".."}
                and os.sep not in name
                and (not os.altsep or os.altsep not in name)
                for name in names
            ):
                raise _FdBackupError("Directory enumeration was ambiguous")
            return sorted(names)
        except _FdBackupError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _FdBackupError("Directory enumeration could not be proven") from exc
        finally:
            if scan_descriptor is not None:
                descriptor_to_close = scan_descriptor
                scan_descriptor = None
                close_ok = self._close_backup_descriptor(descriptor_to_close)
            if not close_ok:
                raise _FdBackupError("Directory enumeration close was unproven")

    def _open_verified_directory_at(
        self,
        parent_descriptor: int,
        name: str,
        expected_stat: os.stat_result,
        *,
        expected_device: int,
        expected_mount_id: int,
        parent_path: Optional[str],
    ) -> Tuple[int, Tuple[int, int, int]]:
        expected_identity = self._filesystem_entry_identity(expected_stat)
        if (
            expected_identity is None
            or not stat.S_ISDIR(expected_stat.st_mode)
            or self._stat_result_is_reparse(expected_stat)
            or expected_stat.st_dev != expected_device
        ):
            raise _FdBackupError("Directory entry classification was unsafe")

        descriptor = None
        try:
            if os.name == "nt":
                descriptor = _open_windows_no_follow(
                    os.path.join(parent_path, name), directory=True
                )
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                flags |= getattr(os, "O_CLOEXEC", 0)
                descriptor = os.open(name, flags, dir_fd=parent_descriptor)
            held_stat = os.fstat(descriptor)
            if (
                self._filesystem_entry_identity(held_stat) != expected_identity
                or self._stat_result_is_reparse(held_stat)
                or held_stat.st_dev != expected_device
                or self._descriptor_mount_id(descriptor) != expected_mount_id
            ):
                raise _FdBackupError("Directory identity changed while opening")
            result = descriptor, expected_identity
            descriptor = None
            return result
        except _FdBackupError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _FdBackupError("Directory could not be opened safely") from exc
        finally:
            if descriptor is not None:
                descriptor_to_close = descriptor
                descriptor = None
                if not self._close_backup_descriptor(descriptor_to_close):
                    raise _FdBackupError("Directory close was unproven")

    def _fd_directory_binding_matches(
        self,
        parent_descriptor: int,
        name: str,
        directory_descriptor: int,
        expected_identity: Tuple[int, int, int],
        expected_mount_id: int,
        *,
        parent_path: Optional[str],
    ) -> bool:
        try:
            bound_stat = self._held_entry_stat(
                parent_descriptor, parent_path, name
            )
            held_stat = os.fstat(directory_descriptor)
            return (
                self._filesystem_entry_identity(bound_stat) == expected_identity
                and self._filesystem_entry_identity(held_stat) == expected_identity
                and not self._stat_result_is_reparse(bound_stat)
                and not self._stat_result_is_reparse(held_stat)
                and self._descriptor_mount_id(directory_descriptor)
                == expected_mount_id
            )
        except (OSError, TypeError, ValueError):
            return False

    @staticmethod
    def _read_held_chunk(descriptor: int) -> bytes:
        """Read up to 1 MiB from a held file.

        On native Windows the C runtime reports a byte-range lock held by
        another process as access denied; ReadFile keeps the Windows error,
        so the lock reads as busy, not as a refused file (issue #608).
        """
        if os.name != "nt":
            return os.read(descriptor, 1024 * 1024)
        import _winapi
        import ctypes
        import msvcrt

        chunk, error_code = _winapi.ReadFile(
            msvcrt.get_osfhandle(descriptor), 1024 * 1024
        )
        if error_code:
            raise ctypes.WinError(error_code)
        return chunk

    def _open_verified_regular_for_read(
        self,
        parent_descriptor: int,
        name: str,
        expected_stat: os.stat_result,
        *,
        expected_device: int,
        expected_mount_id: int,
        parent_path: Optional[str],
    ) -> Tuple[Optional[int], int, Tuple[int, int, int]]:
        expected_identity = self._filesystem_entry_identity(expected_stat)
        if (
            expected_identity is None
            or not stat.S_ISREG(expected_stat.st_mode)
            or self._stat_result_is_reparse(expected_stat)
            or expected_stat.st_dev != expected_device
            or getattr(expected_stat, "st_nlink", 0) != 1
        ):
            raise _FdBackupError("Regular source entry classification was unsafe")

        path_descriptor = None
        read_descriptor = None
        try:
            if os.name == "nt":
                # One no-follow read handle. A special file (for example a
                # Linux FIFO seen over \\wsl.localhost) shows as a reparse
                # point, so it is refused, not opened (issue #608).
                read_descriptor = _open_windows_no_follow(
                    os.path.join(parent_path, name), directory=False
                )
            else:
                path_flags = os.O_PATH | os.O_NOFOLLOW
                path_flags |= getattr(os, "O_CLOEXEC", 0)
                path_descriptor = os.open(
                    name,
                    path_flags,
                    dir_fd=parent_descriptor,
                )
                path_stat = os.fstat(path_descriptor)
                if (
                    self._filesystem_entry_identity(path_stat)
                    != expected_identity
                    or not stat.S_ISREG(path_stat.st_mode)
                    or self._stat_result_is_reparse(path_stat)
                    or path_stat.st_dev != expected_device
                    or getattr(path_stat, "st_nlink", 0) != 1
                    or self._descriptor_mount_id(path_descriptor)
                    != expected_mount_id
                ):
                    raise _FdBackupError(
                        "Regular source identity changed before read"
                    )

                read_flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
                read_flags |= getattr(os, "O_CLOEXEC", 0)
                read_descriptor = os.open(
                    f"/proc/self/fd/{path_descriptor}", read_flags
                )
            read_stat = os.fstat(read_descriptor)
            if (
                self._filesystem_entry_identity(read_stat) != expected_identity
                or not stat.S_ISREG(read_stat.st_mode)
                or self._stat_result_is_reparse(read_stat)
                or read_stat.st_dev != expected_device
                or getattr(read_stat, "st_nlink", 0) != 1
                or self._descriptor_mount_id(read_descriptor)
                != expected_mount_id
            ):
                raise _FdBackupError("Regular source read identity was unproven")
            result = path_descriptor, read_descriptor, expected_identity
            path_descriptor = None
            read_descriptor = None
            return result
        except _FdBackupError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise _FdBackupError("Regular source could not be opened safely") from exc
        finally:
            close_ok = True
            if read_descriptor is not None:
                descriptor_to_close = read_descriptor
                read_descriptor = None
                close_ok = self._close_backup_descriptor(descriptor_to_close)
            if path_descriptor is not None:
                descriptor_to_close = path_descriptor
                path_descriptor = None
                close_ok = (
                    self._close_backup_descriptor(descriptor_to_close)
                    and close_ok
                )
            if not close_ok:
                raise _FdBackupError("Regular source close was unproven")

    def _fd_directory_manifest(
        self,
        directory_descriptor: int,
        *,
        relative_root: str,
        expected_device: int,
        expected_mount_id: int,
        manifest: Dict[str, str],
        held_path: Optional[str],
    ) -> None:
        names = self._fd_directory_names(directory_descriptor, held_path)
        folded_names = [name.casefold() for name in names]
        if len(folded_names) != len(set(folded_names)):
            raise _FdBackupError("Manifest contains case-aliased entries")
        for name in names:
            try:
                entry_stat = self._held_entry_stat(
                    directory_descriptor, held_path, name
                )
            except (OSError, TypeError, ValueError) as exc:
                raise _FdBackupError("Manifest entry could not be classified") from exc
            if (
                self._filesystem_entry_identity(entry_stat) is None
                or self._stat_result_is_reparse(entry_stat)
                or entry_stat.st_dev != expected_device
            ):
                raise _FdBackupError("Manifest entry classification was unsafe")
            relative_path = (
                name if relative_root == "." else f"{relative_root}/{name}"
            )
            child_path = (
                None if held_path is None else os.path.join(held_path, name)
            )
            if stat.S_ISDIR(entry_stat.st_mode):
                child_descriptor = None
                close_ok = True
                try:
                    child_descriptor, child_identity = (
                        self._open_verified_directory_at(
                            directory_descriptor,
                            name,
                            entry_stat,
                            expected_device=expected_device,
                            expected_mount_id=expected_mount_id,
                            parent_path=held_path,
                        )
                    )
                    manifest[f"dir:{relative_path}"] = "directory"
                    self._fd_directory_manifest(
                        child_descriptor,
                        relative_root=relative_path,
                        expected_device=expected_device,
                        expected_mount_id=expected_mount_id,
                        manifest=manifest,
                        held_path=child_path,
                    )
                    if not self._fd_directory_binding_matches(
                        directory_descriptor,
                        name,
                        child_descriptor,
                        child_identity,
                        expected_mount_id,
                        parent_path=held_path,
                    ):
                        raise _FdBackupError(
                            "Manifest directory binding changed"
                        )
                finally:
                    if child_descriptor is not None:
                        descriptor_to_close = child_descriptor
                        child_descriptor = None
                        close_ok = self._close_backup_descriptor(
                            descriptor_to_close
                        )
                    if not close_ok:
                        raise _FdBackupError(
                            "Manifest directory close was unproven"
                        )
                continue
            if (
                not stat.S_ISREG(entry_stat.st_mode)
                or getattr(entry_stat, "st_nlink", 0) != 1
            ):
                raise _FdBackupError("Manifest contains a non-regular entry")
            path_descriptor = None
            read_descriptor = None
            close_ok = True
            try:
                path_descriptor, read_descriptor, entry_identity = (
                    self._open_verified_regular_for_read(
                        directory_descriptor,
                        name,
                        entry_stat,
                        expected_device=expected_device,
                        expected_mount_id=expected_mount_id,
                        parent_path=held_path,
                    )
                )
                digest = hashlib.sha256()
                read_size = 0
                while True:
                    chunk = self._read_held_chunk(read_descriptor)
                    if not isinstance(chunk, bytes):
                        raise _FdBackupError(
                            "Manifest read returned an invalid value"
                        )
                    if not chunk:
                        break
                    digest.update(chunk)
                    read_size += len(chunk)
                final_stat = os.fstat(read_descriptor)
                rebound_stat = self._held_entry_stat(
                    directory_descriptor, held_path, name
                )
                if (
                    self._filesystem_entry_identity(final_stat)
                    != entry_identity
                    or self._filesystem_entry_identity(rebound_stat)
                    != entry_identity
                    or read_size != final_stat.st_size
                ):
                    raise _FdBackupError("Manifest file binding changed")
                manifest[f"file:{relative_path}"] = digest.hexdigest()
            finally:
                if read_descriptor is not None:
                    descriptor_to_close = read_descriptor
                    read_descriptor = None
                    close_ok = self._close_backup_descriptor(
                        descriptor_to_close
                    )
                if path_descriptor is not None:
                    descriptor_to_close = path_descriptor
                    path_descriptor = None
                    close_ok = (
                        self._close_backup_descriptor(descriptor_to_close)
                        and close_ok
                    )
                if not close_ok:
                    raise _FdBackupError(
                        "Manifest file close was unproven"
                    )

    def _manifest_exact_module_guard(
        self,
        entry_guard: Optional[_ExactModuleEntryGuard],
        *,
        report_busy: bool = False,
    ) -> Optional[Dict[str, str]]:
        """Manifest only the directory held by the exact publication guard.

        With ``report_busy``, a transient error (a Windows sharing or lock
        violation, or a temporary POSIX error) raises _ModuleFilesBusy instead
        of returning None: another process holding a file is not a property
        of the module (issue #608).
        """
        if (
            not self._fd_relative_backup_supported()
            or not isinstance(entry_guard, _ExactModuleEntryGuard)
        ):
            return None
        try:
            held_stat = os.fstat(entry_guard.descriptor)
            if (
                self._filesystem_entry_identity(held_stat)
                != entry_guard.identity
                or self._stat_result_is_reparse(held_stat)
            ):
                return None
            mount_id = self._descriptor_mount_id(entry_guard.descriptor)
            if mount_id is None:
                return None
            # Only the path G1 proved names the held tree; a guard without
            # one gets no receipt (issue #608).
            held_path = entry_guard.held_path
            if not held_path:
                return None
            manifest = {"dir:.": "directory"}
            self._fd_directory_manifest(
                entry_guard.descriptor,
                relative_root=".",
                expected_device=held_stat.st_dev,
                expected_mount_id=mount_id,
                manifest=manifest,
                held_path=held_path,
            )
            entry_valid, _entry_reason = (
                self._revalidate_exact_module_entry_guard(entry_guard)
            )
            return manifest if entry_valid else None
        except (_FdBackupError, OSError, TypeError, ValueError) as exc:
            if report_busy:
                cause = exc
                while cause is not None:
                    if is_transient_filesystem_error(cause):
                        raise _ModuleFilesBusy(str(cause)) from exc
                    cause = cause.__cause__
            return None

    @staticmethod
    def _descriptor_relative_sentinel_supported() -> bool:
        """Return whether a no-follow descriptor-relative marker is possible."""
        return (
            os.name != "nt"
            and bool(getattr(os, "O_NOFOLLOW", 0))
            and bool(getattr(os, "O_EXCL", 0))
            and _OPEN_SUPPORTS_DIR_FD
            and _UNLINK_SUPPORTS_DIR_FD
            and _RENAME_SUPPORTS_DIR_FD
            and callable(getattr(os, "write", None))
            and callable(getattr(os, "fsync", None))
        )

    def _write_corrupted_sentinel(
        self,
        module_name: str,
        reason: str,
        *,
        entry_guard: _ExactModuleEntryGuard,
    ) -> bool:
        """Atomically mark only the directory held by ``entry_guard``.

        All creation, writing, and replacement is relative to the held
        directory descriptor.  A lexical-path swap therefore cannot redirect
        the marker into a replacement module, and an existing sentinel symlink
        is replaced as a directory entry without following its target.
        """
        if (
            not isinstance(entry_guard, _ExactModuleEntryGuard)
            or entry_guard.module_name != module_name
            or not self._descriptor_relative_sentinel_supported()
        ):
            return False

        try:
            held_stat = os.fstat(entry_guard.descriptor)
        except (OSError, TypeError, ValueError):
            return False
        if self._stable_directory_identity(held_stat) != entry_guard.identity:
            return False

        temporary_name = f".corrupted.{uuid4().hex}.tmp"
        temporary_descriptor = None
        temporary_created = False
        try:
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0)
            )
            temporary_descriptor = os.open(
                temporary_name,
                flags,
                0o600,
                dir_fd=entry_guard.descriptor,
            )
            temporary_created = True
            payload = f"{reason}\n".encode("utf-8")
            written_total = 0
            while written_total < len(payload):
                written = os.write(
                    temporary_descriptor,
                    payload[written_total:],
                )
                if not isinstance(written, int) or written <= 0:
                    raise OSError("Sentinel write did not make progress")
                written_total += written
            os.fsync(temporary_descriptor)

            descriptor_to_close = temporary_descriptor
            temporary_descriptor = None
            os.close(descriptor_to_close)

            os.rename(
                temporary_name,
                ".corrupted",
                src_dir_fd=entry_guard.descriptor,
                dst_dir_fd=entry_guard.descriptor,
            )
            temporary_created = False
            os.fsync(entry_guard.descriptor)
            return True
        except (OSError, TypeError, ValueError):
            if temporary_descriptor is not None:
                descriptor_to_close = temporary_descriptor
                temporary_descriptor = None
                try:
                    os.close(descriptor_to_close)
                except (OSError, TypeError, ValueError):
                    pass
            if temporary_created:
                try:
                    os.unlink(
                        temporary_name,
                        dir_fd=entry_guard.descriptor,
                    )
                except (OSError, TypeError, ValueError):
                    pass
            return False

    def _build_registry_candidate(
        self,
        prior_registry: Dict[str, Any],
        module_name: str,
        module_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a detached registry candidate without mutating live memory."""
        candidate = deepcopy(prior_registry)
        timestamp = datetime.now().isoformat()
        candidate["modules"][module_name] = {
            "moduleName": module_name,
            "addedDate": timestamp,
            "themes": module_data.get("themes", []),
            "plotObjective": module_data.get("plotObjective", ""),
            "levelRange": module_data.get("levelRange", {"min": 1, "max": 1}),
            "areaCount": len(module_data.get("areas", {})),
            "travelNarration": module_data.get("travelNarration", {}),
        }
        for area_id, area_data in module_data.get("areas", {}).items():
            candidate["areas"][area_id] = {
                **area_data,
                "module": module_name,
                "addedDate": timestamp,
            }
        candidate["lastUpdated"] = timestamp
        return candidate

    @staticmethod
    def _candidate_contains_exact_module(
        registry: Dict[str, Any],
        candidate: Dict[str, Any],
        module_name: str,
        expected_area_ids: set,
    ) -> Tuple[bool, str]:
        if registry != candidate:
            return False, "Registry readback differs from the candidate"
        module_entry = registry.get("modules", {}).get(module_name)
        if not isinstance(module_entry, dict):
            return False, "Exact module entry is missing from registry readback"
        if module_entry.get("moduleName") != module_name:
            return False, "Registry moduleName does not match the exact target"
        registered_area_ids = {
            area_id
            for area_id, area_data in registry.get("areas", {}).items()
            if isinstance(area_data, dict)
            and area_data.get("module") == module_name
        }
        if registered_area_ids != expected_area_ids:
            return False, "Registry readback does not contain the exact target areas"
        return True, ""

    def _restore_or_prove_module_snapshot(
        self,
        module_name: str,
        backup_result: _ModuleBackupResult,
        _reason: str,
        *,
        entry_guard: Optional[_ExactModuleEntryGuard],
    ) -> Optional[bool]:
        """Prove snapshot equality without changing either evidence tree."""
        if entry_guard is None:
            return None
        entry_valid, _entry_reason = (
            self._revalidate_exact_module_entry_guard(entry_guard)
        )
        if not entry_valid:
            return None
        live_manifest = self._manifest_exact_module_guard(entry_guard)
        if live_manifest is None:
            return False
        return (
            backup_result.proven is True
            and backup_result.manifest is not None
            and live_manifest == backup_result.manifest
        )

    def _finish_prewrite_failure(
        self,
        module_name: str,
        backup_result: _ModuleBackupResult,
        prior_registry: Dict[str, Any],
        reason: str,
        *,
        entry_guard: Optional[_ExactModuleEntryGuard],
        cause: Optional[NotJoinedCause] = None,
    ) -> TargetedPublicationResult:
        """Prove prior registry and non-destructive module snapshot equality.

        ``cause`` is carried only on the ``NOT_PUBLISHED`` result.
        """
        registry_ok, registry_reason = self._registry_matches_snapshot(
            prior_registry
        )
        if not registry_ok:
            if entry_guard is not None:
                entry_valid, entry_reason = (
                    self._revalidate_exact_module_entry_guard(entry_guard)
                )
                if not entry_valid:
                    return self._finish_entry_identity_failure(
                        module_name,
                        backup_result,
                        prior_registry,
                        f"{reason}; exact module identity changed: {entry_reason}",
                        registry_attempted=False,
                    )
            backup_manifest = backup_result.manifest
            live_manifest = self._manifest_exact_module_guard(entry_guard)
            if entry_guard is not None:
                entry_valid, entry_reason = (
                    self._revalidate_exact_module_entry_guard(entry_guard)
                )
                if not entry_valid:
                    return self._finish_entry_identity_failure(
                        module_name,
                        backup_result,
                        prior_registry,
                        f"{reason}; exact module identity changed: {entry_reason}",
                        registry_attempted=False,
                    )
            if (
                entry_guard is not None
                and (backup_manifest is None or live_manifest != backup_manifest)
            ):
                self._write_corrupted_sentinel(
                    module_name,
                    f"{reason}; prior registry could not be proven: {registry_reason}",
                    entry_guard=entry_guard,
                )
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                f"{reason}; prior registry could not be proven: {registry_reason}",
            )

        self.world_registry = deepcopy(prior_registry)
        if entry_guard is not None:
            entry_valid, entry_reason = (
                self._revalidate_exact_module_entry_guard(entry_guard)
            )
            if not entry_valid:
                return self._finish_entry_identity_failure(
                    module_name,
                    backup_result,
                    prior_registry,
                    f"{reason}; exact module identity changed: {entry_reason}",
                    registry_attempted=False,
                )
        module_ok = self._restore_or_prove_module_snapshot(
            module_name,
            backup_result,
            reason,
            entry_guard=entry_guard,
        )
        if module_ok is None:
            return self._finish_entry_identity_failure(
                module_name,
                backup_result,
                prior_registry,
                f"{reason}; exact module identity changed during snapshot proof",
                registry_attempted=False,
            )
        if not module_ok:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                f"{reason}; module snapshot equality could not be proven",
                registry_absence_proven=True,
                registry_restoration_proven=True,
            )

        return TargetedPublicationResult(
            PublicationStatus.NOT_PUBLISHED,
            module_name,
            reason,
            registry_absence_proven=True,
            registry_restoration_proven=True,
            module_restoration_proven=True,
            cause=cause,
        )

    def _finish_entry_identity_failure(
        self,
        module_name: str,
        backup_result: _ModuleBackupResult,
        prior_registry: Dict[str, Any],
        reason: str,
        *,
        registry_attempted: bool,
    ) -> TargetedPublicationResult:
        """Restore registry state but never touch a replacement module entry.

        Once the held identity no longer owns the lexical path, path-based
        module rollback cannot prove it is operating on the original tree. The
        result stays indeterminate for manual or later journal-backed
        recovery.
        """
        if registry_attempted:
            registry_ok, registry_reason = self._restore_registry_snapshot(
                prior_registry
            )
        else:
            registry_ok, registry_reason = self._registry_matches_snapshot(
                prior_registry
            )
            if registry_ok:
                self.world_registry = deepcopy(prior_registry)
        if not registry_ok:
            reason = (
                f"{reason}; prior registry state could not be proven: "
                f"{registry_reason}"
            )
        return TargetedPublicationResult(
            PublicationStatus.INDETERMINATE,
            module_name,
            reason,
            registry_restoration_proven=registry_ok,
        )

    def _finish_registry_attempt_failure(
        self,
        module_name: str,
        backup_result: _ModuleBackupResult,
        prior_registry: Dict[str, Any],
        reason: str,
        *,
        entry_guard: Optional[_ExactModuleEntryGuard],
    ) -> TargetedPublicationResult:
        """Restore registry first, then prove module snapshot equality."""
        registry_ok, registry_reason = self._restore_registry_snapshot(
            prior_registry
        )
        if not registry_ok:
            # The candidate module is intentionally left in place. Rolling the
            # module back while registry state is unknown could make a registry
            # that actually committed point at deleted or incompatible files.
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                f"{reason}; prior registry restoration unproven: {registry_reason}",
            )

        if entry_guard is not None:
            entry_valid, entry_reason = (
                self._revalidate_exact_module_entry_guard(entry_guard)
            )
            if not entry_valid:
                return self._finish_entry_identity_failure(
                    module_name,
                    backup_result,
                    prior_registry,
                    f"{reason}; exact module identity changed: {entry_reason}",
                    registry_attempted=False,
                )
        module_ok = self._restore_or_prove_module_snapshot(
            module_name,
            backup_result,
            reason,
            entry_guard=entry_guard,
        )
        if module_ok is None:
            return self._finish_entry_identity_failure(
                module_name,
                backup_result,
                prior_registry,
                f"{reason}; exact module identity changed during snapshot proof",
                registry_attempted=False,
            )
        if not module_ok:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                f"{reason}; module snapshot equality could not be proven",
                registry_absence_proven=True,
                registry_restoration_proven=True,
            )

        return TargetedPublicationResult(
            PublicationStatus.NOT_PUBLISHED,
            module_name,
            reason,
            registry_absence_proven=True,
            registry_restoration_proven=True,
            module_restoration_proven=True,
        )

    def _registry_with_live_publication_identities(
        self, registry: Dict[str, Any], exclude_module: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return a detached conflict view augmented from live module trees.

        A freshly seeded registry can legitimately contain only its ``modules``
        map.  Conflict resolution still needs the identifiers owned by those
        already-live modules.  Rebuild that conflict-only view from disk while
        the caller owns ``module_refresh_lock``; never rewrite the live registry
        as part of discovery. ``exclude_module`` leaves out the live tree that
        a managed import is about to replace (its own old identities).
        """
        from utils.module_refresh_lock import assert_module_refresh_lock_owned

        assert_module_refresh_lock_owned()
        conflict_registry = deepcopy(registry)
        conflict_areas = conflict_registry.get("areas")
        if not isinstance(conflict_areas, dict):
            raise ValueError("World registry shape is invalid")

        support_roots = {
            "backups",
            "campaign_archives",
            "campaign_summaries",
            "conversation_history",
            "default",
            "encounters",
            "logs",
        }
        try:
            with os.scandir(self.modules_dir) as scan:
                entries = sorted(scan, key=lambda entry: entry.name)
        except OSError as exc:
            raise ValueError("Live module roots could not be inspected") from exc

        for entry in entries:
            module_name = entry.name
            if module_name.startswith(".") or module_name in support_roots:
                continue
            if module_name == exclude_module:
                continue
            if entry.is_symlink():
                raise ValueError("Live module root is a link")
            if self._is_symlink_or_reparse(entry.path):
                raise ValueError("Live module root is a reparse point")
            try:
                is_directory = entry.is_dir(follow_symlinks=False)
            except OSError as exc:
                raise ValueError("Live module root could not be inspected") from exc
            if not is_directory:
                continue
            module_path = self._target_module_path(module_name)
            if module_path is None:
                raise ValueError("Live module path is not contained")
            if not os.path.isdir(os.path.join(module_path, "areas")):
                continue

            area_ids, _location_ids, reason = (
                self._module_identity_sets_for_conflict_scan(module_path)
            )
            if area_ids is None:
                raise ValueError(
                    f"Live module identities could not be inspected: {reason}"
                )
            for area_id in area_ids:
                owner = conflict_areas.get(area_id)
                if owner is None:
                    conflict_areas[area_id] = {"module": module_name}
                    continue
                if not isinstance(owner, dict) or owner.get("module") != module_name:
                    raise ValueError(
                        f"Found duplicate live area identity: {area_id}"
                    )

        return conflict_registry

    def build_publication_registry_bytes(
        self, candidate_path, module_name, *, replacing_live=False
    ):
        """Store-free registry preparation for the atomic-publish path (P2b).

        Runs on a freshly built module candidate (utils/module_publish's hidden
        temp workspace) while the caller holds ``module_refresh_lock``: resolves
        area-ID conflicts against the live registry (rewriting the candidate IN
        PLACE), validates the module, and returns the exact ``world_registry.json``
        bytes to commit after the atomic rename. Reuses the proven ModuleStitcher
        registry helpers (_resolve_id_conflicts, _build_registry_candidate, ...)
        with NO ModuleLifecycleStore dependency (that store is deleted in P2c).

        Fail-forward contract: this runs on the HIDDEN candidate BEFORE the module
        is made live. Any raise here aborts the publish with ``modules/<name>``
        never touched -- the player's game is unaffected and the build simply did
        not happen. Never operates on live module state.

        ``replacing_live=True`` is the managed import of an unplayed live
        module: the candidate is a copy of ``modules/<name>`` that will replace
        it, so the occupied final path, a bare registry stub of the name, and
        the live tree's own identities are not conflicts.
        """
        from utils.module_publish import validate_module_name
        from utils.module_refresh_lock import assert_module_refresh_lock_owned

        assert_module_refresh_lock_owned()
        module_name = validate_module_name(module_name)
        candidate = Path(candidate_path).resolve(strict=True)
        modules_root = Path(self.modules_dir).resolve(strict=True)
        # Symlink/reparse safety: reject any link OR reparse point (Windows
        # junction) anywhere in the candidate tree before a normalization writer
        # can follow it out of the workspace. os.path.islink alone misses Windows
        # junctions (they are reparse points, not symlinks), so also test the
        # FILE_ATTRIBUTE_REPARSE_POINT attribute -- restoring the protection the
        # store's create_manifest() provided.
        def _is_link_or_reparse(p):
            if os.path.islink(p):
                return True
            try:
                attrs = os.lstat(p).st_file_attributes
            except (OSError, AttributeError):
                return False
            return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT

        if _is_link_or_reparse(candidate):
            raise ValueError("Managed candidate root is a link or reparse point")
        for root, dirs, files in os.walk(candidate):
            for entry in dirs + files:
                if _is_link_or_reparse(os.path.join(root, entry)):
                    raise ValueError(
                        "Managed candidate contains a link or reparse point"
                    )
        if not replacing_live and os.path.lexists(modules_root / module_name):
            raise FileExistsError("Managed module final path became occupied")

        prior_registry_bytes = Path(self.world_registry_file).read_bytes()
        try:
            prior_registry = json.loads(prior_registry_bytes.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("World registry is not valid UTF-8 JSON") from exc
        if (
            not isinstance(prior_registry, dict)
            or not isinstance(prior_registry.get("modules"), dict)
        ):
            raise ValueError("World registry shape is invalid")
        # Fresh-install registry: reconcile_campaign_state seeds
        # world_registry.json with only a "modules" map (no module has ever
        # published an area), so a genuinely fresh registry has NO "areas" key.
        # Treat ONLY the absent key as an empty map, normalized on this
        # DETACHED parsed copy -- the live file is never rewritten before
        # publication (the only registry write remains the advisory commit
        # after the atomic rename). An "areas" key that is present but not a
        # dict (null, list, string) is still a corrupt registry -> fail closed.
        if "areas" not in prior_registry:
            prior_registry["areas"] = {}
        elif not isinstance(prior_registry["areas"], dict):
            raise ValueError("World registry shape is invalid")
        conflict_registry = self._registry_with_live_publication_identities(
            prior_registry,
            exclude_module=module_name if replacing_live else None,
        )
        if self._registry_references_module(prior_registry, module_name) and not (
            replacing_live and self._is_registry_stub(prior_registry, module_name)
        ):
            raise ValueError("Allocated module name is already registry-owned")

        candidate_text = os.fspath(candidate)
        valid, reason = self._validate_required_publication_files(candidate_text)
        if not valid:
            raise ValueError(reason or "Managed module files are incomplete")
        module_data = self._analyze_module_path(
            candidate_text,
            module_name,
            include_travel_narration=False,
        )
        if not module_data or not module_data.get("areas"):
            raise ValueError("Managed candidate could not be analyzed")

        normalized = self._resolve_id_conflicts(
            module_name,
            module_data,
            registry_snapshot=conflict_registry,
            module_path=candidate_text,
        )
        if normalized:
            self._update_bu_files_after_conflict_resolution(
                module_name,
                module_path=candidate_text,
            )
            module_data = self._analyze_module_path(
                candidate_text,
                module_name,
                include_travel_narration=False,
            )
        if not module_data or not module_data.get("areas"):
            raise ValueError("Managed candidate re-analysis failed")

        valid, reason = self._validate_required_publication_files(candidate_text)
        if not valid:
            raise ValueError(reason or "Normalized module files are incomplete")
        remaining_conflict, conflict_reason, _colliding = (
            self._detect_legacy_publication_conflicts(
                module_name,
                candidate_text,
                conflict_registry,
            )
        )
        if remaining_conflict is None:
            raise ValueError(
                "Managed candidate conflict absence could not be proven: "
                + conflict_reason
            )
        if remaining_conflict:
            raise ValueError(
                "Managed candidate retains conflicting identities: "
                + conflict_reason
            )

        module_data["travelNarration"] = self._generate_travel_narration(
            module_data
        )
        safety = _coerce_module_safety_result(
            self._validate_module_safety(
                module_name,
                module_data,
                module_path=candidate_text,
            )
        )
        if not safety.allows_integration:
            refusal = (
                _ModuleCheckUnavailable
                if safety.status is ModuleSafetyStatus.UNAVAILABLE
                else ValueError
            )
            raise refusal(
                f"Managed module safety {safety.status.value}: "
                f"{safety.reason or 'No reason supplied'}"
            )

        candidate_registry = self._build_registry_candidate(
            prior_registry,
            module_name,
            module_data,
        )
        return (
            json.dumps(
                candidate_registry,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")



    def publish_module(self, module_name: str) -> TargetedPublicationResult:
        """Transactionally publish one exact module; never perform a scan."""
        from utils.module_refresh_lock import module_refresh_lock

        if self._target_module_path(module_name) is None:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                "Invalid or non-contained module name",
            )
        with module_refresh_lock() as acquired:
            if not acquired:
                return TargetedPublicationResult(
                    PublicationStatus.INDETERMINATE,
                    module_name,
                    "Module publication lock timed out",
                )
            return self._publish_module_locked(module_name)

    def publish_module_locked(
        self, module_name: str
    ) -> TargetedPublicationResult:
        """Publish one exact module while the caller owns module_refresh_lock.

        This entry point intentionally does not acquire or release the lock. It
        exists for the builder/publication transaction in ``action_handler``,
        whose caller must keep one uninterrupted ``module_refresh_lock`` scope
        around both module construction and this call. Other callers should use
        :meth:`publish_module`.
        """
        if self._target_module_path(module_name) is None:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                "Invalid or non-contained module name",
            )
        from utils.module_refresh_lock import assert_module_refresh_lock_owned

        assert_module_refresh_lock_owned()
        return self._publish_module_locked(module_name)

    def _publish_module_locked(
        self, module_name: str
    ) -> TargetedPublicationResult:
        """Targeted publication implementation; caller owns refresh lock."""
        module_path = self._target_module_path(module_name)
        if module_path is None:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                "Invalid or non-contained module name",
            )

        entry_state, entry_stat, entry_reason = (
            self._exact_module_entry_state(module_name, module_path)
        )
        if entry_state == "unsafe":
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                f"Exact module entry is unsafe: {entry_reason}",
            )

        entry_guard = None
        if entry_state == "directory":
            if entry_stat is None:
                return TargetedPublicationResult(
                    PublicationStatus.INDETERMINATE,
                    module_name,
                    "Exact module directory identity is unavailable",
                )
            entry_guard, guard_reason = self._acquire_exact_module_entry_guard(
                module_name, module_path, entry_stat
            )
            if entry_guard is None:
                return TargetedPublicationResult(
                    PublicationStatus.INDETERMINATE,
                    module_name,
                    guard_reason,
                )

        try:
            return self._publish_module_locked_with_entry_guard(
                module_name,
                module_path,
                entry_state,
                entry_guard,
            )
        finally:
            self._close_exact_module_entry_guard(entry_guard)

    def _publish_module_locked_with_entry_guard(
        self,
        module_name: str,
        module_path: str,
        entry_state: str,
        entry_guard: Optional[_ExactModuleEntryGuard],
    ) -> TargetedPublicationResult:
        """Publish while revalidating one held lexical entry at boundaries."""

        if (
            entry_state == "directory"
            and not self._fd_relative_backup_supported()
        ):
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                (
                    "Descriptor-relative module backup is unsupported; "
                    "publication stopped before registry access"
                ),
            )

        prior_registry, registry_reason = self._read_registry_snapshot()
        if prior_registry is None:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                registry_reason,
            )
        entry_valid, entry_reason = self._revalidate_publication_entry(
            module_name,
            module_path,
            entry_state,
            entry_guard,
        )
        if not entry_valid:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                f"Exact module entry changed during registry read: {entry_reason}",
            )

        # This fresh read proves the prior disk state. Use it as the stable
        # in-memory baseline while candidate construction remains detached.
        self.world_registry = deepcopy(prior_registry)

        # A bare stub names the module without integrating it; publish it
        # through the unregistered path, whose candidate replaces the stub.
        referenced = self._registry_references_module(
            prior_registry, module_name
        ) and not self._is_registry_stub(prior_registry, module_name)
        exact_entry = prior_registry.get("modules", {}).get(module_name)
        if referenced:
            if entry_state != "directory" or os.path.exists(
                os.path.join(module_path, ".corrupted")
            ):
                return TargetedPublicationResult(
                    PublicationStatus.INDETERMINATE,
                    module_name,
                    "Registry references the module but its directory is missing or corrupted",
                )

            files_valid, files_reason = self._validate_required_publication_files(
                module_path
            )
            module_data = (
                self.analyze_module(module_name, include_travel_narration=False)
                if files_valid
                else None
            )
            registered_area_ids = {
                area_id
                for area_id, area_data in prior_registry.get("areas", {}).items()
                if isinstance(area_data, dict)
                and area_data.get("module") == module_name
            }
            aliases = {
                key
                for key, module_entry in prior_registry.get("modules", {}).items()
                if isinstance(module_entry, dict)
                and module_entry.get("moduleName") == module_name
            }
            analyzed_area_ids = (
                set(module_data.get("areas", {}))
                if isinstance(module_data, dict)
                else set()
            )
            exact_publication_proven = (
                files_valid
                and isinstance(exact_entry, dict)
                and exact_entry.get("moduleName") == module_name
                and aliases == {module_name}
                and bool(analyzed_area_ids)
                and analyzed_area_ids == registered_area_ids
                and exact_entry.get("areaCount") == len(analyzed_area_ids)
            )
            if exact_publication_proven:
                entry_valid, entry_reason = self._revalidate_publication_entry(
                    module_name,
                    module_path,
                    entry_state,
                    entry_guard,
                )
                if not entry_valid:
                    return TargetedPublicationResult(
                        PublicationStatus.INDETERMINATE,
                        module_name,
                        (
                            "Exact registered module identity changed before "
                            f"publication proof: {entry_reason}"
                        ),
                    )
                self.world_registry = deepcopy(prior_registry)
                return TargetedPublicationResult(
                    PublicationStatus.PUBLISHED,
                    module_name,
                    "Existing exact module files and registered areas were freshly verified",
                )
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                (
                    "Registry references the module but full exact publication proof failed"
                    + (f": {files_reason}" if not files_valid else "")
                ),
            )

        if entry_state == "absent":
            return TargetedPublicationResult(
                PublicationStatus.NOT_PUBLISHED,
                module_name,
                "Exact module directory does not exist",
                registry_absence_proven=True,
                registry_restoration_proven=True,
                module_restoration_proven=True,
            )
        if entry_state != "directory":
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                "Exact module directory state could not be proven",
            )
        if os.path.exists(os.path.join(module_path, ".corrupted")):
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                "Exact module is marked .corrupted; forensic state was retained",
                registry_absence_proven=True,
                registry_restoration_proven=True,
            )

        files_refused = ""
        try:
            conflict_state, conflict_reason, conflicting_modules = (
                self._detect_legacy_publication_conflicts(
                    module_name,
                    module_path,
                    prior_registry,
                )
            )
        except _ModuleFilesBusy:
            # Busy is not a property of the module: the scan stays
            # inconclusive, so the result is INDETERMINATE (issue #608).
            conflict_state, conflict_reason, conflicting_modules = (
                None,
                _MODULE_FILES_BUSY_REASON,
                (),
            )
        except _ModuleFilesRefused as exc:
            conflict_state, conflict_reason, conflicting_modules = None, "", ()
            files_refused = str(exc) or "Module reset masters could not be read"
        entry_valid, entry_reason = self._revalidate_publication_entry(
            module_name,
            module_path,
            entry_state,
            entry_guard,
        )
        if not entry_valid:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                "Exact module identity changed during conflict inspection: "
                f"{entry_reason}",
            )
        if files_refused:
            # Nothing has been written yet: the module's own files failed a
            # check, so it is reported as not joined (issue #609).
            return TargetedPublicationResult(
                PublicationStatus.NOT_PUBLISHED,
                module_name,
                files_refused,
                registry_absence_proven=True,
                registry_restoration_proven=True,
                module_restoration_proven=True,
                cause=NotJoinedCause.CHECK_REFUSED,
            )
        if conflict_state is None:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                conflict_reason,
            )
        if conflict_state is True:
            return TargetedPublicationResult(
                PublicationStatus.IMPORT_REQUIRED,
                module_name,
                conflict_reason,
                registry_absence_proven=True,
                registry_restoration_proven=True,
                module_restoration_proven=True,
                conflicting_modules=conflicting_modules,
            )

        # The receipt is one manifest of the held tree. This path never writes
        # module files, so the failure proofs need only these hashes to tell
        # NOT_PUBLISHED from INDETERMINATE; no copy is kept (issue #565).
        try:
            receipt_manifest = self._manifest_exact_module_guard(
                entry_guard, report_busy=True
            )
        except _ModuleFilesBusy:
            # Busy is not a property of the module: nothing was refused or
            # written, and the next start tries again (issue #608).
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                _MODULE_FILES_BUSY_REASON,
            )
        if not isinstance(receipt_manifest, dict):
            backup_result = _ModuleBackupResult(
                proven=False,
                reason="Module manifest could not be proven",
            )
        elif not any(key.startswith("file:") for key in receipt_manifest):
            backup_result = _ModuleBackupResult(
                proven=False,
                reason="Backup contained no regular files",
            )
        else:
            backup_result = _ModuleBackupResult(
                proven=True,
                manifest=receipt_manifest,
            )
        backup_dir = backup_result
        entry_valid, entry_reason = self._revalidate_publication_entry(
            module_name,
            module_path,
            entry_state,
            entry_guard,
        )
        if not entry_valid:
            return TargetedPublicationResult(
                PublicationStatus.INDETERMINATE,
                module_name,
                (
                    "Exact module identity changed while creating its backup: "
                    f"{entry_reason}"
                ),
            )
        if (
            backup_result.proven is not True
            or not isinstance(backup_result.manifest, dict)
        ):
            backup_reason = backup_result.reason or (
                "A complete descriptor-bound snapshot receipt could not be created"
            )
            return TargetedPublicationResult(
                PublicationStatus.NOT_PUBLISHED,
                module_name,
                backup_reason,
                registry_absence_proven=True,
                registry_restoration_proven=True,
                module_restoration_proven=True,
                cause=NotJoinedCause.CHECK_REFUSED,
            )

        registry_attempted = False
        try:
            valid, validation_reason = self._validate_required_publication_files(
                module_path
            )
            if not valid:
                return self._finish_prewrite_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    validation_reason,
                    entry_guard=entry_guard,
                    cause=NotJoinedCause.CHECK_REFUSED,
                )

            module_data = self.analyze_module(
                module_name, include_travel_narration=False
            )
            if not module_data or not module_data.get("areas"):
                return self._finish_prewrite_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    "Exact module could not be analyzed",
                    entry_guard=entry_guard,
                    cause=NotJoinedCause.CHECK_REFUSED,
                )

            area_ids = set(module_data.get("areas", {}))

            module_data["travelNarration"] = self._generate_travel_narration(
                module_data
            )
            safety_result = _coerce_module_safety_result(
                self._validate_module_safety(module_name, module_data)
            )
            if not safety_result.allows_integration:
                if safety_result.status is ModuleSafetyStatus.UNAVAILABLE:
                    print(
                        f"Module {module_name} safety validation unavailable - "
                        "deferring integration for a later retry"
                    )
                else:
                    print(
                        f"Module {module_name} failed safety validation - "
                        "skipping integration"
                    )
                return self._finish_prewrite_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    (
                        f"Module safety {safety_result.status.value}: "
                        f"{safety_result.reason or 'No reason supplied'}"
                    ),
                    entry_guard=entry_guard,
                    cause=(
                        NotJoinedCause.CHECK_UNAVAILABLE
                        if safety_result.status is ModuleSafetyStatus.UNAVAILABLE
                        else NotJoinedCause.CHECK_REFUSED
                    ),
                )

            candidate = self._build_registry_candidate(
                prior_registry, module_name, module_data
            )
            entry_valid, entry_reason = self._revalidate_publication_entry(
                module_name,
                module_path,
                entry_state,
                entry_guard,
            )
            if not entry_valid:
                return self._finish_entry_identity_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    (
                        "Exact module identity changed before registry write: "
                        f"{entry_reason}"
                    ),
                    registry_attempted=False,
                )
            registry_attempted = True
            try:
                write_result = safe_write_json(
                    self.world_registry_file, candidate, stop_if_read_only=True
                )
            except Exception as exc:
                return self._finish_registry_attempt_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    f"Candidate registry write raised: {exc}",
                    entry_guard=entry_guard,
                )
            entry_valid, entry_reason = self._revalidate_publication_entry(
                module_name,
                module_path,
                entry_state,
                entry_guard,
            )
            if not entry_valid:
                return self._finish_entry_identity_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    (
                        "Exact module identity changed during registry write: "
                        f"{entry_reason}"
                    ),
                    registry_attempted=True,
                )
            if write_result is not True:
                return self._finish_registry_attempt_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    "Candidate registry write did not report success",
                    entry_guard=entry_guard,
                )

            readback, readback_reason = self._read_registry_snapshot()
            if readback is None:
                return self._finish_registry_attempt_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    f"Candidate registry readback failed: {readback_reason}",
                    entry_guard=entry_guard,
                )
            entry_valid, entry_reason = self._revalidate_publication_entry(
                module_name,
                module_path,
                entry_state,
                entry_guard,
            )
            if not entry_valid:
                return self._finish_entry_identity_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    (
                        "Exact module identity changed during registry readback: "
                        f"{entry_reason}"
                    ),
                    registry_attempted=True,
                )
            candidate_ok, candidate_reason = self._candidate_contains_exact_module(
                readback, candidate, module_name, area_ids
            )
            if not candidate_ok:
                return self._finish_registry_attempt_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    candidate_reason,
                    entry_guard=entry_guard,
                )

            entry_valid, entry_reason = self._revalidate_publication_entry(
                module_name,
                module_path,
                entry_state,
                entry_guard,
            )
            if not entry_valid:
                return self._finish_entry_identity_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    (
                        "Exact module identity changed before publication: "
                        f"{entry_reason}"
                    ),
                    registry_attempted=True,
                )

            # Only the exact, freshly-proven candidate may become live memory.
            self.world_registry = deepcopy(readback)
            print(f"Successfully integrated module: {module_name}")
            print(f"  - Added {len(area_ids)} areas")
            return TargetedPublicationResult(
                PublicationStatus.PUBLISHED,
                module_name,
                "Exact module and areas were written and verified",
            )
        except Exception as exc:
            reason = f"Publication pipeline raised: {exc}"
            if registry_attempted:
                return self._finish_registry_attempt_failure(
                    module_name,
                    backup_dir,
                    prior_registry,
                    reason,
                    entry_guard=entry_guard,
                )
            return self._finish_prewrite_failure(
                module_name,
                backup_dir,
                prior_registry,
                reason,
                entry_guard=entry_guard,
            )

    def integrate_module(self, module_name: str) -> bool:
        """Compatibility adapter for callers that still require a boolean."""
        return self.publish_module(module_name).published

    @staticmethod
    def _capture_area_documents_from_path(
        module_path: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Capture ordinary live area JSON before deterministic ID rewrites."""
        areas_path = os.path.join(module_path, "areas")
        documents: Dict[str, Dict[str, Any]] = {}
        for filename in sorted(os.listdir(areas_path)):
            if not filename.endswith(".json") or filename.endswith("_BU.json"):
                continue
            path = os.path.join(areas_path, filename)
            value = safe_json_load(path)
            if not isinstance(value, dict):
                raise ValueError(f"Area document is not an object: {filename}")
            documents[filename] = deepcopy(value)
        return documents

    def _apply_exact_id_mapping_to_module(
        self,
        module_path: str,
        id_mapping: Dict[str, str],
    ) -> None:
        """Replace exact JSON string IDs throughout one owned candidate tree."""
        if not id_mapping:
            return
        for root, directories, filenames in os.walk(module_path, followlinks=False):
            directories.sort()
            filenames.sort()
            for filename in filenames:
                if not filename.endswith(".json") or filename.endswith("_BU.json"):
                    continue
                path = os.path.join(root, filename)
                value = safe_json_load(path)
                if value is None:
                    raise ValueError(f"Could not read JSON during ID rewrite: {path}")
                updated = self._recursively_update_ids_in_json(value, id_mapping)
                if updated != value and safe_write_json(path, updated) is not True:
                    raise OSError(f"Could not persist ID rewrite: {path}")

    def _resolve_id_conflicts(
        self,
        module_name: str,
        module_data: Dict[str, Any],
        registry_snapshot: Optional[Dict[str, Any]] = None,
        *,
        module_path: str,
    ) -> int:
        """Resolve area ID and location ID conflicts by modifying the new module"""
        try:
            conflicts_resolved = 0
            registry = (
                registry_snapshot
                if registry_snapshot is not None
                else self.world_registry
            )
            # Conflict discovery needs a working copy. Mutating the live
            # registry here would violate the publication commit boundary.
            existing_areas = deepcopy(registry.get('areas', {}))
            original_area_documents = self._capture_area_documents_from_path(
                module_path
            )
            exact_reference_mapping: Dict[str, str] = {}

            # Check for area ID conflicts
            conflicting_areas = []
            candidate_area_ids = list(module_data.get('areas', {}))
            for area_id in candidate_area_ids:
                if area_id in existing_areas:
                    conflicting_areas.append(area_id)

            # Allocation must avoid BOTH live IDs and every other area already
            # present in this candidate. Otherwise HH001 conflicting with a
            # live module can be renamed onto the candidate's own HH002.json,
            # overwriting that file before the old one is removed.
            occupied_areas = deepcopy(existing_areas)
            for area_id in candidate_area_ids:
                occupied_areas.setdefault(area_id, {"module": module_name})

            if conflicting_areas:
                print(f"  - Found {len(conflicting_areas)} area ID conflicts: {conflicting_areas}")

                # Generate new unique area IDs
                for old_area_id in conflicting_areas:
                    new_area_id = self._generate_unique_area_id(
                        old_area_id, occupied_areas, module_name
                    )

                    # Update area file
                    original_area = next(
                        (
                            area
                            for area in original_area_documents.values()
                            if area.get("areaId") == old_area_id
                        ),
                        None,
                    )
                    if not self._update_area_id_in_files(
                        module_path, old_area_id, new_area_id
                    ):
                        raise RuntimeError(
                            f"Could not rewrite conflicting area {old_area_id}"
                        )
                    print(f"    - Renamed area {old_area_id} -> {new_area_id}")
                    conflicts_resolved += 1
                    exact_reference_mapping[old_area_id] = new_area_id
                    if isinstance(original_area, dict):
                        for location in original_area.get("locations", []):
                            if not isinstance(location, dict):
                                continue
                            old_location = location.get("locationId")
                            if isinstance(old_location, str) and old_location.startswith(
                                old_area_id
                            ):
                                exact_reference_mapping[old_location] = (
                                    old_location.replace(old_area_id, new_area_id, 1)
                                )

                    # Reserve each allocation for later candidate conflicts.
                    occupied_areas[new_area_id] = {"module": module_name}

            self._apply_exact_id_mapping_to_module(
                module_path,
                exact_reference_mapping,
            )

            current_area_documents = self._capture_area_documents_from_path(
                module_path
            )

            # Check for location ID conflicts globally
            location_conflicts = self._resolve_and_reprefix_location_ids(
                module_name,
                module_path,
                current_area_documents,
                registry_snapshot=registry,
            )
            conflicts_resolved += location_conflicts

            return conflicts_resolved

        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Error resolving ID conflicts: {e}")
            raise
    
    def _generate_unique_area_id(self, original_id: str, existing_areas: Dict[str, Any], module_name: str) -> str:
        """Generate a unique area ID by appending suffix"""
        # Extract base and number if present
        base_match = re.match(r'^([A-Z]+)(\d*)$', original_id)
        if base_match:
            base = base_match.group(1)
            num = base_match.group(2)
            start_num = int(num) if num else 1
        else:
            base = original_id
            start_num = 1
        
        # Find next available number
        for i in range(start_num + 1, start_num + 1000):  # Reasonable limit
            new_id = f"{base}{i:03d}"
            if new_id not in existing_areas:
                return new_id
        
        # Fallback: append module name
        return f"{original_id}_{module_name}"
    
    def _update_area_id_in_files(self, module_path: str, old_id: str, new_id: str) -> bool:
        """Update area ID in area file and any references"""
        try:
            # Track location ID mappings for party tracker update
            location_id_mapping = {}

            # Find and update the area file. New modules store areas under
            # module_path/areas/; legacy modules used the module root. (issue #128)
            area_file = os.path.join(module_path, "areas", f"{old_id}.json")
            if not os.path.exists(area_file):
                area_file = os.path.join(module_path, f"{old_id}.json")  # legacy fallback
            if os.path.exists(area_file):
                # Load, update, and save area file
                area_data = safe_json_load(area_file)
                if area_data and 'areaId' in area_data:
                    area_data['areaId'] = new_id

                    # Update location IDs within the area
                    for location in area_data.get('locations', []):
                        old_loc_id = location.get('locationId', '')
                        if old_loc_id.startswith(old_id):
                            new_loc_id = old_loc_id.replace(old_id, new_id, 1)
                            location['locationId'] = new_loc_id
                            # Track the mapping for party_tracker update
                            location_id_mapping[old_loc_id] = new_loc_id

                        # Note: areaConnectivityId contains location IDs which are independent
                        # of area IDs/names, so we do NOT update them when renaming areas

                    # Update map room IDs if map exists
                    map_data = area_data.get('map', {})
                    if map_data and 'rooms' in map_data:
                        for room in map_data['rooms']:
                            old_room_id = room.get('id', '')
                            if old_room_id.startswith(old_id):
                                new_room_id = old_room_id.replace(old_id, new_id, 1)
                                room['id'] = new_room_id

                                # Update connections
                                if 'connections' in room:
                                    updated_connections = []
                                    for conn in room['connections']:
                                        if conn.startswith(old_id):
                                            updated_connections.append(conn.replace(old_id, new_id, 1))
                                        else:
                                            updated_connections.append(conn)
                                    room['connections'] = updated_connections

                    # Save updated area file in the SAME directory the old one was
                    # found in (areas/ for new modules, root for legacy). (issue #128)
                    new_area_file = os.path.join(os.path.dirname(area_file), f"{new_id}.json")
                    if not safe_write_json(new_area_file, area_data):
                        raise OSError("Could not write normalized area file")
                    if safe_json_load(new_area_file) != area_data:
                        raise OSError("Normalized area file failed exact readback")

                    # Remove old file
                    os.remove(area_file)

                    # Keep the reset snapshot addressable under the normalized
                    # area identity. The later BU refresh copies the fully
                    # rewritten primary over this renamed file. Without this
                    # rename, conflict resolution leaves an orphaned
                    # <old_area>_BU.json and creates no reset point for the
                    # published <new_area>.json.
                    old_area_backup = os.path.join(
                        os.path.dirname(area_file), f"{old_id}_BU.json"
                    )
                    if os.path.lexists(old_area_backup):
                        new_area_backup = os.path.join(
                            os.path.dirname(area_file), f"{new_id}_BU.json"
                        )
                        if os.path.lexists(new_area_backup):
                            raise FileExistsError(
                                "Normalized area backup path is occupied"
                            )
                        os.rename(old_area_backup, new_area_backup)

                    # Update corresponding map file if it exists
                    old_map_file = os.path.join(module_path, f"map_{old_id}.json")
                    if os.path.exists(old_map_file):
                        new_map_file = os.path.join(module_path, f"map_{new_id}.json")
                        os.rename(old_map_file, new_map_file)
                        old_map_backup = os.path.join(
                            module_path, f"map_{old_id}_BU.json"
                        )
                        if os.path.lexists(old_map_backup):
                            new_map_backup = os.path.join(
                                module_path, f"map_{new_id}_BU.json"
                            )
                            if os.path.lexists(new_map_backup):
                                raise FileExistsError(
                                    "Normalized map backup path is occupied"
                                )
                            os.rename(old_map_backup, new_map_backup)

                    # Update party_tracker.json if location IDs were changed
                    if location_id_mapping:
                        self._update_party_tracker_location_ids(location_id_mapping, module_path)

                    return True

            return False

        except Exception as e:
            print(f"Error updating area ID from {old_id} to {new_id}: {e}")
            return False
    
    def _update_party_tracker_location_ids(self, location_id_mapping: Dict[str, str], module_path: str) -> bool:
        """
        Update party_tracker.json with new location IDs after area ID changes.

        Args:
            location_id_mapping: Dictionary mapping old location IDs to new location IDs
            module_path: Path to the module being updated

        Returns:
            True if party_tracker was updated, False otherwise
        """
        try:
            # Extract module name from module path
            module_name = os.path.basename(module_path)

            # Load party_tracker.json from root directory using absolute path
            party_tracker_path = self.party_tracker_file
            if not os.path.exists(party_tracker_path):
                return False

            party_tracker = safe_json_load(party_tracker_path)
            if not party_tracker:
                return False

            # Get the active module name (normalize spaces to underscores)
            active_module = party_tracker.get('module', '').replace(' ', '_')

            # Only update if the party is currently in this module
            if active_module != module_name:
                return False

            # Get current location ID
            world_conditions = party_tracker.get('worldConditions', {})
            current_location_id = world_conditions.get('currentLocationId')

            # Check if current location ID needs to be updated
            if current_location_id and current_location_id in location_id_mapping:
                new_location_id = location_id_mapping[current_location_id]
                world_conditions['currentLocationId'] = new_location_id
                party_tracker['worldConditions'] = world_conditions

                # Save updated party tracker
                safe_write_json(party_tracker_path, party_tracker)
                print(f"DEBUG: [Module Stitcher] Updated party_tracker.json: {current_location_id} -> {new_location_id} (area ID change)")
                return True

            return False

        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Failed to update party_tracker.json: {e}")
            return False

    def _resolve_and_reprefix_location_ids(
        self,
        module_name: str,
        module_path: str,
        pre_reprefix_area_documents: Dict[str, Dict[str, Any]],
        registry_snapshot: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Ensures all location IDs in a new module are globally unique.
        If any conflict is found, it re-prefixes ALL locations in the new module.

        Args:
            module_name: Name of the module being integrated
            module_path: Path to the module directory
            pre_reprefix_area_documents: Area JSON documents read from the
                candidate after area renames and before the location re-prefix
        """
        print(f"DEBUG: [Module Stitcher] Validating global uniqueness of location IDs for {module_name}...")

        # 1. Get all existing location IDs from the live module trees named by
        # the detached conflict registry. Do not reconstruct an area filename
        # from its JSON areaId: legacy packages may not have matching stems,
        # and silently skipping that lookup would miss a real collision.
        all_existing_loc_ids = set()
        registry = (
            registry_snapshot
            if registry_snapshot is not None
            else self.world_registry
        )
        existing_module_names = {
            area_info.get("module")
            for area_info in registry.get("areas", {}).values()
            if isinstance(area_info, dict)
            and isinstance(area_info.get("module"), str)
            and area_info.get("module") != module_name
        }
        for existing_module_name in sorted(existing_module_names):
            existing_path = self._target_module_path(existing_module_name)
            if existing_path is None:
                raise ValueError("Registered module path is unsafe")
            state, _entry_stat, state_reason = self._exact_module_entry_state(
                existing_module_name, existing_path
            )
            # Preserve compatibility with a registry entry whose package was
            # removed. There is no live identity to collide with in that case.
            if state == "absent":
                continue
            if state != "directory":
                raise ValueError(
                    f"Registered module path is unsafe: {state_reason}"
                )
            _area_ids, location_ids, reason = (
                self._module_identity_sets_for_conflict_scan(existing_path)
            )
            if location_ids is None:
                raise ValueError(
                    f"Live module identities could not be inspected: {reason}"
                )
            all_existing_loc_ids.update(location_ids)

        # 2. Get all location IDs from the NEW module
        new_module_loc_ids = set()
        new_module_areas_path = os.path.join(module_path, "areas")
        if not os.path.exists(new_module_areas_path):
            return 0
            
        for area_file in os.listdir(new_module_areas_path):
            if area_file.endswith(".json"):
                area_data = safe_json_load(os.path.join(new_module_areas_path, area_file))
                if area_data:
                    for loc in area_data.get('locations', []):
                        if loc.get('locationId'):
                            new_module_loc_ids.add(loc.get('locationId'))

        # 3. Check for any overlap
        conflicting_ids = all_existing_loc_ids.intersection(new_module_loc_ids)
        
        if not conflicting_ids:
            print(f"DEBUG: [Module Stitcher] All location IDs in {module_name} are unique.")
            return 0

        print(f"DEBUG: [Module Stitcher] WARNING: Found {len(conflicting_ids)} conflicting location IDs: {list(conflicting_ids)[:5]}...")

        # 4. If conflict exists, re-prefix the ENTIRE new module
        print(f"DEBUG: [Module Stitcher] Conflict found. Re-prefixing all locations in {module_name} to ensure uniqueness.")
        
        # INT-H2: derive the next free prefix index from the FULL alpha prefix
        # of every existing location ID (e.g. 'AA01' -> 'AA'), not just the
        # first character. Reading only loc_id[0] treats 'AA01' as prefix 'A',
        # so start_index lands inside the already-used range and the new module
        # can be handed an already-used two-letter prefix.
        # The module's own current prefixes count too: a new prefix equal to
        # one of its old ones (CMS001 C->H while HLF001 still holds H01)
        # would be rewritten again by the module-wide old->new reference
        # mapping below, giving duplicate ids.
        max_prefix_index = -1
        for loc_id in all_existing_loc_ids | new_module_loc_ids:
            m = re.match(r'^([A-Za-z]+)\d', loc_id or '')
            if m:
                max_prefix_index = max(max_prefix_index, _location_prefix_to_index(m.group(1)))

        start_index = max_prefix_index + 1
        
        sorted_new_area_files = sorted(os.listdir(new_module_areas_path))
        conflicts_resolved = 0
        
        for i, area_filename in enumerate(sorted_new_area_files):
            if not area_filename.endswith(".json") or area_filename.endswith("_BU.json"):
                continue

            # Generate a new, globally unique prefix
            new_prefix = _location_index_to_prefix(start_index + i)
            area_file_path = os.path.join(new_module_areas_path, area_filename)
            area_data = safe_json_load(area_file_path)
            
            if area_data:
                print(f"DEBUG: [Module Stitcher] Applying new prefix '{new_prefix}' to area {area_data.get('areaId')}")
                # Use ModuleGenerator instead of ModuleBuilder for update_area_with_prefix
                from core.generators.module_generator import ModuleGenerator
                temp_generator = ModuleGenerator()
                updated_area_data = temp_generator.update_area_with_prefix(area_data, new_prefix)
                if safe_write_json(area_file_path, updated_area_data) is not True:
                    raise OSError(
                        f"Could not persist location-ID rewrite: {area_filename}"
                    )
                if safe_json_load(area_file_path) != updated_area_data:
                    raise OSError(
                        f"Location-ID rewrite failed readback: {area_filename}"
                    )
                conflicts_resolved += len(updated_area_data.get('locations', []))

        # After re-prefixing, we need to update all references to the old IDs
        self._update_all_location_references(
            module_name,
            pre_reprefix_area_documents,
            module_path=module_path,
        )

        return conflicts_resolved
    
    def _recursively_update_ids_in_json(self, data: Any, id_mapping: Dict[str, str], exclude_keys: List[str] = None) -> Any:
        """
        Safely traverse JSON and apply exact ID mappings to object keys and
        string values while skipping values beneath ``exclude_keys``.

        Module context indexes areas and locations by their IDs, so rewriting
        only values leaves those authoritative lookup keys stale after conflict
        normalization. Key collisions fail closed rather than discarding data.
        """
        if exclude_keys is None:
            exclude_keys = []

        if isinstance(data, dict):
            new_dict = {}
            for key, value in data.items():
                new_key = id_mapping.get(key, key)
                if new_key in new_dict:
                    raise ValueError(
                        f"ID rewrite creates duplicate object key: {new_key}"
                    )
                if key in exclude_keys:
                    new_dict[new_key] = value  # Keep original value without recursion
                else:
                    new_dict[new_key] = self._recursively_update_ids_in_json(
                        value, id_mapping, exclude_keys
                    )
            return new_dict
        elif isinstance(data, list):
            return [self._recursively_update_ids_in_json(item, id_mapping, exclude_keys) for item in data]
        elif isinstance(data, str):
            # Apply mapping if the string is an ID that needs mapping
            return id_mapping.get(data, data)
        else:
            # Return non-string, non-collection types as is
            return data

    def _update_all_location_references(
        self,
        module_name: str,
        pre_reprefix_area_documents: Dict[str, Dict[str, Any]],
        *,
        module_path: str,
    ) -> None:
        """
        Update all internal references to location IDs after re-prefixing using a safe, recursive JSON traversal.
        This function avoids blind text replacement to prevent corrupting external references like 'areaConnectivityId'.
        Runs only on a publication candidate tree; any failure raises.
        """
        id_mapping = {}

        # Build ID mapping from the area documents read from the candidate
        # before the location re-prefix.
        if not pre_reprefix_area_documents:
            raise ValueError(
                "No original area documents are available for ID rewrite"
            )

        current_areas_path = os.path.join(module_path, "areas")

        # Compare captured original data with current re-prefixed files.
        for filename, backup_data in sorted(pre_reprefix_area_documents.items()):
            if filename.endswith('.json') and not filename.endswith('_BU.json'):
                # The filename in the current dir should be the same
                current_file = os.path.join(current_areas_path, filename)

                if os.path.exists(current_file):
                    current_data = safe_json_load(current_file)

                    if backup_data and current_data:
                        # INT-H3: map old->new locationId POSITIONALLY, not by
                        # location name. update_area_with_prefix re-prefixes IDs
                        # in place, preserving the locations array's order and
                        # count, so backup[i] corresponds to current[i]. Two
                        # locations can share a name (e.g. 'Corridor'); keying
                        # the mapping by name silently drops one of them and
                        # leaves its cross-file references pointing at the old ID.
                        backup_locs = backup_data.get('locations', [])
                        current_locs = current_data.get('locations', [])
                        for b_loc, c_loc in zip(backup_locs, current_locs):
                            if not isinstance(b_loc, dict) or not isinstance(c_loc, dict):
                                continue
                            old_id = b_loc.get('locationId')
                            new_id = c_loc.get('locationId')
                            if old_id and new_id and old_id != new_id:
                                id_mapping[old_id] = new_id

        if not id_mapping:
            print(f"DEBUG: [Module Stitcher] No location ID changes detected for {module_name}. Skipping reference update.")
            return

        print(f"DEBUG: [Module Stitcher] Built ID mapping with {len(id_mapping)} entries for {module_name}. Applying updates...")

        # Walk through all JSON files in the module and apply the mapping safely
        for root, _, files in os.walk(module_path):
            for filename in files:
                if filename.endswith('.json') and not filename.endswith('.bak') and not filename.endswith('_BU.json'):
                    file_path = os.path.join(root, filename)
                    data = safe_json_load(file_path)
                    if not data:
                        continue

                    # Apply the recursive update (id_mapping only contains current module IDs, so external links are safe)
                    updated_data = self._recursively_update_ids_in_json(data, id_mapping)

                    # Check if any changes were made before writing
                    if data != updated_data:
                        if safe_write_json(file_path, updated_data) is not True:
                            raise OSError(
                                f"Could not persist ID references: {file_path}"
                            )
                        if safe_json_load(file_path) != updated_data:
                            raise OSError(
                                f"ID reference readback differs: {file_path}"
                            )
                        print(f"DEBUG: [Module Stitcher] Updated location ID references in {os.path.relpath(file_path, module_path)}")

    def _validate_module_safety(
        self,
        module_name: str,
        module_data: Dict[str, Any],
        *,
        module_path: Optional[str] = None,
    ) -> ModuleSafetyResult:
        """Validate a module and return an explicit integration-gate result."""
        try:
            # Basic structural validation
            if not module_data.get('areas'):
                print(f"  - Warning: Module {module_name} has no areas")
                return ModuleSafetyResult(
                    ModuleSafetyStatus.UNSAFE,
                    "Module has no areas",
                )
            
            # Check for malicious file names or paths
            module_path = module_path or os.path.join(
                self.modules_dir, module_name
            )
            if not self._validate_file_structure(module_path):
                return ModuleSafetyResult(
                    ModuleSafetyStatus.UNSAFE,
                    "Module failed file-structure validation",
                )
            
            # AI-powered content validation
            ai_result = _coerce_module_safety_result(
                self._ai_validate_content_safety(module_data)
            )
            if not ai_result.allows_integration:
                return ai_result
            
            # Schema validation using existing validator
            if not self._validate_against_schemas(module_path):
                return ModuleSafetyResult(
                    ModuleSafetyStatus.UNSAFE,
                    "Module failed schema validation",
                )
            
            return ModuleSafetyResult(
                ModuleSafetyStatus.SAFE,
                "All module safety checks passed",
            )
            
        except Exception as e:
            print(f"Error validating module safety: {e}")
            return ModuleSafetyResult(
                ModuleSafetyStatus.UNAVAILABLE,
                f"Module safety pipeline failed: {e}",
            )
    
    def _validate_file_structure(self, module_path: str) -> bool:
        """Validate file structure for safety"""
        try:
            # Check for suspicious file patterns
            dangerous_patterns = [
                r'\.\./',  # Directory traversal
                r'^/',     # Absolute paths
                r'\.exe$', r'\.bat$', r'\.sh$',  # Executables
                r'\.dll$', r'\.so$',  # Libraries
            ]
            
            for root, dirs, files in os.walk(module_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.modules_dir)
                    
                    for pattern in dangerous_patterns:
                        if re.search(pattern, relative_path, re.IGNORECASE):
                            print(f"  - Security risk: Suspicious file pattern '{relative_path}'")
                            return False
                    
                    # Check file size (prevent extremely large files)
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > 10 * 1024 * 1024:  # 10MB limit
                            print(f"  - Security risk: File too large '{relative_path}' ({file_size} bytes)")
                            return False
                    except:
                        continue
            
            return True
            
        except Exception as e:
            print(f"Error validating file structure: {e}")
            return False
    
    def _ai_validate_content_safety(
        self, module_data: Dict[str, Any]
    ) -> ModuleSafetyResult:
        """Return a typed T033 content-safety verdict.

        Provider/runtime failures and malformed responses are
        ``UNAVAILABLE``, never ``SAFE`` and never fabricated ``UNSAFE``
        verdicts.  The integration caller blocks both non-safe states while
        preserving unavailable modules for a later retry.
        """
        try:
            # Prepare content summary for AI review
            content_summary = {
                "plotObjective": module_data.get('plotObjective', ''),
                "themes": module_data.get('themes', []),  # All themes
                "areaDescriptions": []
            }
            
            # Add area descriptions (full content)
            for area_id, area_data in module_data.get('areas', {}).items():
                desc = area_data.get('areaDescription', '')
                if desc:
                    content_summary["areaDescriptions"].append(desc)
            
            # AI content safety prompt
            safety_prompt = f"""Review this fantasy adventure module content for safety and appropriateness:

{json.dumps(content_summary, indent=2)}

Check for:
1. Excessively violent or graphic content
2. Inappropriate adult themes
3. Hate speech or discriminatory content
4. Malicious instructions or code
5. Copyright violations

Respond with JSON:
{{"safe": true/false, "reason": "explanation if unsafe"}}"""
            
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                summ_config = config.DM_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_config = config.DM_SUMM_LMSTUDIO
            else:  # legacy
                summ_config = config.DM_SUMM_LEGACY

            response = capture_and_fanout("T033", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=[
                    {"role": "system", "content": "You are a content safety reviewer for family-friendly fantasy gaming content. Be strict but reasonable in your assessment."},
                    {"role": "user", "content": safety_prompt}
                ],
                model=summ_config["model"],
                temperature=0.1,
                **{k: v for k, v in summ_config.items() if k != "model"})

            ai_response = response.choices[0].message.content
            try:
                safety_result = json.loads(ai_response)
            except (json.JSONDecodeError, TypeError) as e:
                warning(
                    f"Safety check returned invalid JSON ({e}); integration deferred",
                    category="module_integration",
                )
                print(
                    "  - AI safety validation response unparseable; "
                    "integration deferred"
                )
                return ModuleSafetyResult(
                    ModuleSafetyStatus.UNAVAILABLE,
                    f"Safety validator returned malformed JSON: {e}",
                )

            if not isinstance(safety_result, dict):
                warning(
                    "Safety check returned a non-object JSON value; integration deferred",
                    category="module_integration",
                )
                return ModuleSafetyResult(
                    ModuleSafetyStatus.UNAVAILABLE,
                    "Safety validator response was not a JSON object",
                )

            safe_value = safety_result.get('safe')
            if not isinstance(safe_value, bool):
                warning(
                    "Safety check omitted a boolean 'safe' verdict; integration deferred",
                    category="module_integration",
                )
                return ModuleSafetyResult(
                    ModuleSafetyStatus.UNAVAILABLE,
                    "Safety validator did not return a boolean 'safe' verdict",
                )

            reason_value = safety_result.get('reason')
            reason = reason_value if isinstance(reason_value, str) else ""
            if not safe_value:
                reason = reason or "Unspecified content safety issue"
                print(f"  - Content safety issue: {reason}")
                return ModuleSafetyResult(ModuleSafetyStatus.UNSAFE, reason)

            return ModuleSafetyResult(
                ModuleSafetyStatus.SAFE,
                reason or "Safety validator approved the module",
            )

        except Exception as e:
            error(
                f"Safety check API/runtime call failed: {e}; integration deferred",
                category="module_integration",
            )
            print(
                f"Warning: AI content validation failed: {e} "
                "(integration deferred)"
            )
            return ModuleSafetyResult(
                ModuleSafetyStatus.UNAVAILABLE,
                f"Safety validator unavailable: {e}",
            )
    
    def _validate_against_schemas(self, module_path: str) -> bool:
        """Validate module files against schemas"""
        try:
            # Use the existing validator
            from core.validation.validate_module_files import ModuleValidator
            
            schema_dir = Path(__file__).resolve().parents[2] / "schemas"
            validator = ModuleValidator(module_path, str(schema_dir))

            # Run validation (suppress output)
            import sys
            from io import StringIO

            old_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
                # VAL-C2 downgrade: use the lenient legacy locationfile_schema
                # (strict=False) for the PASS/FAIL gate. The strict 21-field
                # per-location contract (locationfile_schema_strict.json) empirically
                # rejected valid AI-generated modules -- Keep_of_Doom scored 0.737
                # under strict (FAIL, triggering integration rollback) vs 0.944 under
                # the legacy schema (PASS on main) -- because AI locations legitimately
                # omit some optional fields and use multi-word skill DCs. Matching
                # main's proven strict=False behavior prevents valid modules from being
                # rolled back. The strict schema remains in-repo for opt-in diagnostics.
                results = validator.validate_all_files(strict=False)
                success_rate = validator.get_success_rate()
            finally:
                sys.stdout = old_stdout
            
            # Check if validation passed (allow some failures for non-critical files)
            if success_rate < 0.8:  # 80% success rate minimum
                print(f"  - Schema validation failed: {success_rate:.1%} success rate")
                return False
            
            return True
            
        except Exception as e:
            print(f"Warning: Schema validation failed: {e}")
            return False
    
    _IMPORT_WORKSPACE_PREFIX = ".module_import_"

    def _managed_import_refusal(self, module_name: str) -> Optional[str]:
        """Why an installed module counts as played, or None when unplayed.

        A played module is never rewritten. Value checks only:
        ``tracker``: the party's module is this one;
        ``live_state``: the live record holds a place, occupant or quest of
        it (typed ids ``kind:<Module>/...``);
        ``archive``: a campaign archive or summary names it as its
        moduleName, or the campaign lists it as completed or current;
        ``saved_games``: its folder holds a save.
        An unreadable record counts as played (the module is left alone).
        """
        try:
            tracker = safe_json_load(self.party_tracker_file) if os.path.exists(
                self.party_tracker_file
            ) else {}
        except Exception:
            return "tracker"
        if isinstance(tracker, dict) and str(
            tracker.get("module") or ""
        ).replace(" ", "_") == module_name:
            return "tracker"

        live_path = os.path.join(self.root_dir, "live_state.json")
        if os.path.exists(live_path):
            try:
                live = safe_json_load(live_path)
            except Exception:
                live = None
            if not isinstance(live, dict):
                return "live_state"
            # Engine shape (NQL docs/LIVE_STATE.md, version 3): ``places`` is a
            # list of typed-id strings (as core/nql/occupants.py:754 reads it);
            # occupants and quests are records with ``id`` (and ``location``).
            # Characters and map.visited stand at places, so they are covered.
            typed_ids = list(live.get("places") or [])
            for occupant in live.get("occupants") or []:
                if isinstance(occupant, dict):
                    typed_ids += [occupant.get("id"), occupant.get("location")]
            for quest in live.get("quests") or []:
                if isinstance(quest, dict):
                    typed_ids.append(quest.get("id"))
            for typed_id in typed_ids:
                if isinstance(typed_id, str) and (
                    typed_id.partition(":")[2].split("/", 1)[0] == module_name
                ):
                    return "live_state"

        for record_dir in ("campaign_archives", "campaign_summaries"):
            directory = os.path.join(self.modules_dir, record_dir)
            if not os.path.isdir(directory):
                continue
            for filename in sorted(os.listdir(directory)):
                if not filename.endswith(".json"):
                    continue
                try:
                    record = safe_json_load(os.path.join(directory, filename))
                except Exception:
                    return "archive"
                if isinstance(record, dict) and record.get("moduleName") == module_name:
                    return "archive"
        campaign_path = os.path.join(self.modules_dir, "campaign.json")
        if os.path.exists(campaign_path):
            try:
                campaign = safe_json_load(campaign_path)
            except Exception:
                return "archive"
            if isinstance(campaign, dict) and (
                campaign.get("currentModule") == module_name
                or module_name in (campaign.get("completedModules") or [])
            ):
                return "archive"

        saves = os.path.join(self.modules_dir, module_name, "saved_games")
        if os.path.isdir(saves) and os.listdir(saves):
            return "saved_games"
        return None

    @staticmethod
    def _area_location_ids(module_path: str) -> Dict[str, List[Any]]:
        """Location ids per live area file, in file order."""
        areas_dir = os.path.join(module_path, "areas")
        out = {}
        for filename in sorted(os.listdir(areas_dir)):
            if filename.endswith(".json") and not filename.endswith("_BU.json"):
                area = safe_json_load(os.path.join(areas_dir, filename))
                locations = area.get("locations", []) if isinstance(area, dict) else []
                out[filename] = [
                    location.get("locationId")
                    for location in locations
                    if isinstance(location, dict)
                ]
        return out

    def _settle_import_workspace(self, workspace: Path, module_name: str) -> bool:
        """Leave the module live and remove the workspace; never lose the module.

        If the live entry is missing while the retired original is in the
        workspace (a stop between the two renames), the original is renamed
        back first. The workspace is removed only once ``modules/<name>``
        exists. Returns whether the workspace is gone.
        """
        from utils.module_publish import _replace_entry

        live_path = Path(self.modules_dir) / module_name
        retired = workspace / "retired" / module_name
        if not os.path.lexists(live_path) and os.path.lexists(retired):
            _replace_entry(retired, live_path)
            warning(
                f"Managed import of {module_name} was interrupted between its "
                "renames; the original module was put back",
                category="module_integration",
            )
        if not os.path.lexists(live_path):
            error(
                f"Managed import workspace {workspace.name} kept: {module_name} "
                "is not live and no original was found in it",
                category="module_integration",
            )
            return False
        shutil.rmtree(workspace)
        return True

    def _recover_managed_imports_locked(self) -> int:
        """Settle every managed import workspace a stopped run left behind."""
        settled = 0
        try:
            entries = sorted(os.listdir(self.modules_dir))
        except OSError:
            return settled
        for entry in entries:
            if not entry.startswith(self._IMPORT_WORKSPACE_PREFIX):
                continue
            workspace = Path(self.modules_dir) / entry
            try:
                marker = safe_json_load(str(workspace / "import.json"))
            except Exception:
                marker = None
            module_name = marker.get("module") if isinstance(marker, dict) else None
            try:
                if module_name is None:
                    # The marker is written before anything is moved, so a
                    # workspace without one holds no original; one with a
                    # retired entry anyway is kept for a person to look at.
                    retired_dir = workspace / "retired"
                    if retired_dir.is_dir() and os.listdir(retired_dir):
                        error(
                            f"Managed import workspace {entry} has no marker "
                            "but holds a retired entry; kept",
                            category="module_integration",
                        )
                        continue
                    shutil.rmtree(workspace)
                    settled += 1
                    continue
                if self._target_module_path(module_name) is None:
                    error(
                        f"Managed import workspace {entry} names an unsafe module",
                        category="module_integration",
                    )
                    continue
                if self._settle_import_workspace(workspace, module_name):
                    settled += 1
            except Exception as exc:
                error(
                    f"Managed import workspace {entry} could not be settled: {exc}",
                    category="module_integration",
                )
        return settled

    def _refuse_links_while_copying(
        self, directory: str, names: List[str]
    ) -> List[str]:
        """copytree ``ignore`` hook: raise on a link or reparse point.

        copytree copies a Windows junction's target inline, so a link is
        refused as copytree reaches it, on every platform (issue #608).
        """
        for name in names:
            path = os.path.join(directory, name)
            if self._is_symlink_or_reparse(path):
                raise ValueError(f"Module contains a link or reparse point: {path}")
        return []

    def _import_colliding_module_locked(self, module_name: str) -> Dict[str, Any]:
        """Join an unplayed module whose ids collide, renumbering a copy.

        The caller owns module_refresh_lock. A played module is refused. The
        live folder is copied into a hidden workspace, the copy goes through
        the hidden-candidate publication path (re-prefix, validation, T032,
        T033, registry bytes), and only then is it swapped in: live ->
        retired, candidate -> live, registry bytes. Any failure before the
        swap leaves the live folder as it was.
        """
        from utils.module_publish import (
            _replace_entry,
            _replace_exact_bytes,
            _sync_directory,
        )
        from utils.transient_filesystem import retry_transient_filesystem

        refusal = self._managed_import_refusal(module_name)
        if refusal:
            return {"status": "refused", "refused_because": refusal}

        live_path = Path(self.modules_dir) / module_name
        workspace = Path(self.modules_dir) / (
            f"{self._IMPORT_WORKSPACE_PREFIX}{uuid4().hex}"
        )
        candidate = workspace / "candidate" / module_name
        retired = workspace / "retired" / module_name
        try:
            (workspace / "candidate").mkdir(parents=True)
            (workspace / "retired").mkdir()
            (workspace / "import.json").write_text(
                json.dumps({"module": module_name}), encoding="utf-8"
            )
            if self._is_symlink_or_reparse(str(live_path)):
                raise ValueError(
                    f"Module folder is a link or reparse point: {live_path}"
                )
            shutil.copytree(
                live_path,
                candidate,
                symlinks=True,
                ignore=self._refuse_links_while_copying,
            )
            copied = {
                os.path.relpath(os.path.join(directory, filename), candidate)
                for directory, _dirs, filenames in os.walk(candidate)
                for filename in filenames
            }
            before = self._area_location_ids(str(candidate))
            registry_bytes = self.build_publication_registry_bytes(
                candidate, module_name, replacing_live=True
            )
            after = self._area_location_ids(str(candidate))
            # The rewrite's own .bak copies hold intermediate ids; the
            # original stays in the workspace until the swap, so they are
            # not kept in the module.
            for directory, _dirs, filenames in os.walk(candidate):
                for filename in filenames:
                    path = os.path.join(directory, filename)
                    if filename.endswith(".bak") and (
                        os.path.relpath(path, candidate) not in copied
                    ):
                        os.remove(path)
            renumbered = sum(
                old != new
                for area in before
                for old, new in zip(before[area], after.get(area, []))
            )
            # N4: a module without a declaration is typed (T122) on the
            # candidate, where its ids are final, so the declaration is
            # synced and swapped in with it. Never raises; a failure
            # imports it untyped.
            from core.generators.module_declaration import type_joining_module

            type_joining_module(candidate, module_name)
            _sync_directory(candidate)
            _replace_entry(live_path, retired)
            _replace_entry(candidate, live_path)
        except Exception as exc:
            warning(
                f"Managed import of {module_name} did not complete; the module "
                f"is left as it was: {exc}",
                category="module_integration",
            )
            try:
                self._settle_import_workspace(workspace, module_name)
            except Exception as settle_exc:
                error(
                    f"Managed import workspace {workspace.name} kept for the "
                    f"next scan: {settle_exc}",
                    category="module_integration",
                )
            if isinstance(exc, _ModuleCheckUnavailable):
                # The safety check gave no verdict: told apart from a refusal
                # so the startup line does not blame the module (issue #613).
                return {
                    "status": "failed",
                    "refused_because": NotJoinedCause.CHECK_UNAVAILABLE.value,
                }
            return {"status": "failed", "refused_because": "import_failed"}

        # The renumbered module is live; nothing below may undo that.
        try:
            retry_transient_filesystem(
                lambda: _replace_exact_bytes(
                    Path(self.world_registry_file), registry_bytes
                )
            )
            self.world_registry = json.loads(registry_bytes.decode("utf-8"))
        except Exception as exc:
            error(
                f"Module {module_name} was renumbered and is live, but its "
                f"registry write failed; the next scan integrates it: {exc}",
                category="module_integration",
            )
        try:
            self._settle_import_workspace(workspace, module_name)
        except Exception as exc:
            warning(
                f"Managed import workspace {workspace.name} not removed: {exc}",
                category="module_integration",
            )
        return {"status": "imported", "renumbered": renumbered}

    def scan_and_integrate_new_modules(
        self, priority_module: Optional[str] = None
    ) -> List[str]:
        """Scan/integrate under the shared module-publication boundary.

        ``priority_module`` (the party's module) is integrated first, so a
        module that collides with it is the one left unjoined.
        """
        from utils.module_refresh_lock import module_refresh_lock

        with module_refresh_lock() as acquired:
            if not acquired:
                warning(
                    "Module integration skipped: refresh lock timeout",
                    category="module_integration",
                )
                return []
            from utils.commit_state import recover_incomplete_refresh_commit
            from utils.module_lifecycle import ModuleLifecycleStore, RecoveryStatus

            recover_incomplete_refresh_commit()
            recovery = ModuleLifecycleStore(self.modules_dir).recover()
            if recovery.status is RecoveryStatus.INDETERMINATE:
                warning(
                    "Module integration blocked by indeterminate lifecycle recovery",
                    category="module_integration",
                )
                return []
            return self._scan_and_integrate_new_modules_locked(
                priority_module=priority_module
            )

    def _scan_and_integrate_new_modules_locked(
        self, priority_module: Optional[str] = None
    ) -> List[str]:
        """Perform the scan while the caller owns module refresh."""
        integrated_modules = []
        self.import_required = []
        self.imported = []
        self.not_joined = []
        
        try:
            self._recover_managed_imports_locked()
            # Detect new modules
            new_modules = self.detect_new_modules()
            if priority_module in new_modules:
                new_modules.remove(priority_module)
                new_modules.insert(0, priority_module)
            
            if not new_modules:
                info("STATE: No new modules detected.", category="module_integration")
                return integrated_modules
            
            print(f"Found {len(new_modules)} new modules to integrate...")
            
            # Integrate each new module
            for module_name in new_modules:
                try:
                    result = self.publish_module_locked(module_name)
                    if result.status is PublicationStatus.PUBLISHED:
                        integrated_modules.append(module_name)
                        # N4: a module joining without a declaration is
                        # typed (T122) in its live folder, still under the
                        # refresh lock. Never raises; a failure joins it untyped.
                        from core.generators.module_declaration import type_joining_module

                        type_joining_module(Path(self.modules_dir) / module_name, module_name)
                    elif result.status is PublicationStatus.IMPORT_REQUIRED:
                        collides_with = list(result.conflicting_modules)
                        outcome = self._import_colliding_module_locked(
                            module_name
                        )
                        if outcome["status"] == "imported":
                            info(
                                f"Module {module_name} joined after renumbering "
                                f"{outcome['renumbered']} location ids "
                                f"(they collided with {', '.join(collides_with)})",
                                category="module_integration",
                            )
                            integrated_modules.append(module_name)
                            self.imported.append(
                                {
                                    "module": module_name,
                                    "collides_with": collides_with,
                                    "renumbered": outcome["renumbered"],
                                }
                            )
                        else:
                            warning(
                                f"Module {module_name} is installed but not joined "
                                f"({outcome['refused_because']}): {result.reason}",
                                category="module_integration",
                            )
                            self.import_required.append(
                                {
                                    "module": module_name,
                                    "collides_with": collides_with,
                                    "refused_because": outcome["refused_because"],
                                }
                            )
                    elif result.status is PublicationStatus.NOT_PUBLISHED:
                        warning(
                            f"Module {module_name} is installed but not joined: "
                            f"{result.reason}",
                            category="module_integration",
                        )
                        # A module removed during the scan is not "installed".
                        if os.path.isdir(os.path.join(self.modules_dir, module_name)):
                            self.not_joined.append(
                                {
                                    "module": module_name,
                                    "reason": result.reason,
                                    "cause": getattr(result.cause, "value", None),
                                }
                            )
                    elif result.status is PublicationStatus.INDETERMINATE:
                        error(
                            f"Publication state indeterminate for {module_name}: "
                            f"{result.reason}",
                            category="module_integration",
                        )
                        # The player is told only what is proven: still
                        # installed, and not joined in the registry (issue #608).
                        # A read-only registry is a proven fact at this
                        # moment, and the player can fix it (issue #654).
                        if self._module_proven_unjoined(module_name):
                            cause = (
                                NotJoinedCause.REGISTRY_READ_ONLY
                                if replace_target_is_read_only(self.world_registry_file)
                                else NotJoinedCause.UNPROVEN
                            )
                            self.not_joined.append(
                                {
                                    "module": module_name,
                                    "reason": result.reason,
                                    "cause": cause.value,
                                }
                            )
                except Exception as e:
                    print(f"Failed to integrate module {module_name}: {e}")
                    continue
            
            if integrated_modules:
                print(f"Successfully integrated {len(integrated_modules)} modules: {', '.join(integrated_modules)}")
            
            return integrated_modules
            
        except Exception as e:
            print(f"Error during module scanning and integration: {e}")
            return integrated_modules
    
    def get_world_overview(self) -> Dict[str, Any]:
        """Get overview of the current world state"""
        try:
            modules = self.world_registry.get('modules', {})
            areas = self.world_registry.get('areas', {})
            
            overview = {
                "totalModules": len(modules),
                "totalAreas": len(areas),
                "moduleList": list(modules.keys()),
                "areasByModule": {},
                "moduleDetails": {},
                "isolatedModules": True  # Flag indicating modules are isolated
            }
            
            # Group areas by module
            for area_id, area_data in areas.items():
                module = area_data.get('module', 'Unknown')
                if module not in overview["areasByModule"]:
                    overview["areasByModule"][module] = []
                overview["areasByModule"][module].append({
                    "areaId": area_id,
                    "areaName": area_data.get('areaName', ''),
                    "areaType": area_data.get('areaType', '')
                })
            
            # Add module details with travel narration
            for module_name, module_data in modules.items():
                overview["moduleDetails"][module_name] = {
                    "plotObjective": module_data.get('plotObjective', ''),
                    "levelRange": module_data.get('levelRange', {}),
                    "areaCount": module_data.get('areaCount', 0),
                    "travelNarration": module_data.get('travelNarration', {}).get('travelNarration', '')
                }
            
            return overview
            
        except Exception as e:
            print(f"Error getting world overview: {e}")
            return {}
    
    def get_module_travel_narration(self, module_name: str) -> Dict[str, Any]:
        """Get travel narration for a specific module"""
        try:
            modules = self.world_registry.get('modules', {})
            module_data = modules.get(module_name, {})
            
            travel_narration = module_data.get('travelNarration', {})
            if not travel_narration:
                # Generate fallback narration
                return {
                    "travelNarration": f"The party travels to the {module_name.replace('_', ' ')} region, where new adventures await.",
                    "dmGuidance": "Present this as a clean transition to the new module.",
                    "generatedDate": datetime.now().isoformat()
                }
            
            return travel_narration
            
        except Exception as e:
            print(f"Error getting travel narration for {module_name}: {e}")
            return {}
    
    def _disk_fallback_module_list(self) -> List[Dict[str, Any]]:
        """Minimal module listing derived from on-disk public module directories,
        used only when the registry names no modules (issue #167 class). Analysis
        is detection-only (no travel narration, no registration, no writes)."""
        support_roots = {
            'backups', 'campaign_archives', 'campaign_summaries',
            'conversation_history', 'default', 'encounters', 'logs',
        }
        listing: List[Dict[str, Any]] = []
        modules_dir = 'modules'
        if not os.path.isdir(modules_dir):
            return listing
        for name in sorted(os.listdir(modules_dir)):
            if name.startswith('.') or name in support_roots:
                continue
            if not os.path.isdir(os.path.join(modules_dir, name)):
                continue
            try:
                detected = self.analyze_module(name, include_travel_narration=False)
            except Exception as detect_error:
                print(f"Warning: Could not analyze module {name}: {detect_error}")
                continue
            areas = (detected or {}).get('areas') or {}
            if not areas:
                continue
            listing.append({
                "moduleName": name,
                "plotObjective": '',
                "levelRange": {},
                "areaCount": len(areas),
                "locationCount": sum(
                    area.get('locationCount', 0) for area in areas.values()
                    if isinstance(area, dict)
                ),
                "plotPointCount": 0,
                "addedDate": '',
                "hasTravel": False,
            })
        if listing:
            print(
                f"[MODULES] Registry names no modules; listing {len(listing)} "
                "module(s) found on disk."
            )
        return listing

    def get_available_modules(self) -> List[Dict[str, Any]]:
        """Get list of all available modules with basic info"""
        try:
            modules = self.world_registry.get('modules', {})
            all_areas = self.world_registry.get('areas', {})  # Get all areas once
            module_list = []
            
            for module_name, module_data in modules.items():
                # Get total location count for this module
                total_locations = 0
                module_areas = 0
                for area_id, area_data in all_areas.items():
                    if area_data.get('module') == module_name:
                        module_areas += 1
                        total_locations += area_data.get('locationCount', 0)
                
                # Get plot point count from themes or plotPoints
                plot_point_count = 0
                # Check for themes (plot hooks)
                themes = module_data.get('themes', [])
                if themes:
                    plot_point_count = len(themes)
                
                # Also check for plotPoints if themes is empty
                if plot_point_count == 0:
                    plot_points = module_data.get('plotPoints', [])
                    plot_point_count = len(plot_points)
                
                module_list.append({
                    "moduleName": module_name,
                    "plotObjective": module_data.get('plotObjective', ''),
                    "levelRange": module_data.get('levelRange', {}),
                    "areaCount": module_areas if module_areas > 0 else module_data.get('areaCount', 0),
                    "locationCount": total_locations,  # Add new data
                    "plotPointCount": plot_point_count,  # Add new data
                    "addedDate": module_data.get('addedDate', ''),
                    "hasTravel": bool(module_data.get('travelNarration'))
                })

            # Issue #167 class: an empty (fresh/auto-created) registry used to
            # make the toolkit/web module list silently empty even with real
            # modules on disk -- the same registry-shadow defect fixed in the
            # startup scan. Fall back to a disk-derived listing so on-disk
            # modules are never invisible; registry data stays preferred when
            # it has entries.
            if not module_list:
                module_list = self._disk_fallback_module_list()

            return sorted(module_list, key=lambda x: x['addedDate'])
            
        except Exception as e:
            print(f"Error getting available modules: {e}")
            return []
    
    def _update_bu_files_after_conflict_resolution(
        self,
        module_name: str,
        *,
        module_path: str,
    ) -> int:
        """
        Update BU (backup) files with corrected location IDs after conflict resolution.
        This ensures BU files match the corrected files for all JSON files that have BU versions.
        """
        try:
            updated_count = 0
            
            # Walk through all directories in the module
            for root, dirs, files in os.walk(module_path):
                for filename in files:
                    if filename.endswith('.json') and not filename.endswith('_BU.json'):
                        json_file = os.path.join(root, filename)
                        bu_file = os.path.join(root, filename.replace('.json', '_BU.json'))
                        
                        # Check if a BU version exists
                        if os.path.exists(bu_file):
                            # Copy the corrected file to its BU version
                            try:
                                import shutil
                                shutil.copy2(json_file, bu_file)
                                updated_count += 1
                                rel_path = os.path.relpath(bu_file, module_path)
                                print(f"DEBUG: [Module Stitcher] Updated BU file: {rel_path}")
                            except Exception as e:
                                print(f"DEBUG: [Module Stitcher] ERROR: Failed to update BU file {bu_file}: {e}")
            
            return updated_count
            
        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Failed to update BU files: {e}")
            return 0


# Utility functions for integration
def get_module_stitcher():
    """Get or create module stitcher instance"""
    return ModuleStitcher()

def scan_for_new_modules():
    """Utility function to scan for new modules"""
    stitcher = get_module_stitcher()
    return stitcher.scan_and_integrate_new_modules()

def get_world_status():
    """Get current world registry status"""
    stitcher = get_module_stitcher()
    return stitcher.get_world_overview()

def get_module_travel_info(module_name: str):
    """Get travel narration for a specific module"""
    stitcher = get_module_stitcher()
    return stitcher.get_module_travel_narration(module_name)

def list_available_modules():
    """Get list of all available modules"""
    stitcher = get_module_stitcher()
    return stitcher.get_available_modules()

if __name__ == "__main__":
    # Command line interface for testing
    print("=== Module Stitcher ===")
    stitcher = ModuleStitcher()
    
    # Scan for new modules
    print("\nScanning for new modules...")
    integrated = stitcher.scan_and_integrate_new_modules()
    
    # Show world overview
    print("\nWorld Overview:")
    overview = stitcher.get_world_overview()
    print(json.dumps(overview, indent=2))
