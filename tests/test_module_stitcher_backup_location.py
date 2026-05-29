"""Tests for T3-4 (INT-C2): module integration backups live OUTSIDE the
module directory, and are cleaned up on successful integration.

The legacy code path created the backup at:

    modules/<module_name>/backup_pre_integration_<ts>/

This is wrong for two reasons:

  1. Rollback would target a sibling of the live module files -- if the
     live files are themselves the corruption, a rollback could overwrite
     the backup mid-recovery, or the validator might walk the backup as
     if it were live content.
  2. The backup is only useful during the narrow window of
     `integrate_module`. Leaving it behind forever pollutes the module
     directory and bloats disk over many runs.

T3-4 changes the backup destination to:

    modules/.integration_backups/<module_name>_<timestamp>/

This dotted-name directory is:
  - Outside any specific module dir (so rollback restores from a safe
    sibling location).
  - Already filtered out of module discovery by the dotted-name check
    at module_stitcher.py line ~171 (`item.startswith('.')`), so the
    backup is never picked up as a module.
  - Cleaned up at the end of a successful integration via
    `_cleanup_backup`.

The cleanup helper must be idempotent so the rollback path added in
T3-5 can call it safely even when the backup is already gone.
"""

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import module_stitcher as ms_module
from core.generators.module_stitcher import ModuleStitcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare_stitcher(tmp_path) -> ModuleStitcher:
    """Allocate a ModuleStitcher without running __init__ (which constructs
    a real OpenAI client and touches the filesystem).
    """
    stitcher = object.__new__(ModuleStitcher)
    stitcher.modules_dir = str(tmp_path / "modules")
    stitcher.root_dir = str(tmp_path)
    stitcher.world_registry_file = str(tmp_path / "modules" / "world_registry.json")
    stitcher.party_tracker_file = str(tmp_path / "party_tracker.json")
    stitcher.world_registry = {
        "modules": {},
        "areas": {},
        "lastUpdated": "2026-05-22T00:00:00",
    }
    os.makedirs(stitcher.modules_dir, exist_ok=True)
    return stitcher


def _seed_minimal_module(modules_dir: str, module_name: str) -> str:
    """Create a tiny module on disk with one JSON file so the backup
    function has something to copy. Returns the module path.
    """
    module_path = os.path.join(modules_dir, module_name)
    os.makedirs(module_path, exist_ok=True)
    # One root-level JSON file.
    with open(os.path.join(module_path, f"{module_name}_module.json"),
              "w", encoding="utf-8") as fh:
        fh.write('{"moduleName": "%s"}' % module_name)
    return module_path


# ---------------------------------------------------------------------------
# Test 1: backup destination is OUTSIDE the module directory
# ---------------------------------------------------------------------------

def test_create_module_backup_writes_outside_module_dir(tmp_path):
    """_create_module_backup must place the backup under
    modules/.integration_backups/<name>_<ts>/, NOT inside
    modules/<name>/.

    A backup inside the module dir is the INT-C2 bug -- rollback would
    target a sibling of the corruption, and discovery walks could
    confuse the backup for live content.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "TestBackupModule"
    module_path = _seed_minimal_module(stitcher.modules_dir, module_name)

    backup_dir = stitcher._create_module_backup(module_name)

    assert backup_dir, (
        "_create_module_backup returned an empty/None path -- the function "
        "must produce a backup directory when at least one file is backed up."
    )

    # The backup must NOT be inside the module dir.
    abs_module = os.path.realpath(module_path)
    abs_backup = os.path.realpath(backup_dir)
    assert not abs_backup.startswith(abs_module + os.sep) and abs_backup != abs_module, (
        f"Backup is INSIDE the module directory (INT-C2 bug). "
        f"module={abs_module} backup={abs_backup}"
    )

    # The backup must live under modules/.integration_backups/<name>_<ts>/.
    expected_parent = os.path.realpath(
        os.path.join(stitcher.modules_dir, ".integration_backups")
    )
    assert os.path.dirname(abs_backup) == expected_parent, (
        f"Backup must live directly under modules/.integration_backups/, "
        f"got parent={os.path.dirname(abs_backup)} expected={expected_parent}"
    )

    # The leaf name must include the module name so multiple modules
    # don't collide.
    leaf = os.path.basename(abs_backup)
    assert leaf.startswith(module_name + "_"), (
        f"Backup leaf '{leaf}' must start with '{module_name}_' so backups "
        f"for different modules don't collide in .integration_backups/."
    )

    # And the backup actually contains the seeded file.
    assert os.path.exists(os.path.join(backup_dir, f"{module_name}_module.json")), (
        "Backup should contain the seeded module JSON file."
    )


# ---------------------------------------------------------------------------
# Test 2: the .integration_backups dir is not picked up as a module
# ---------------------------------------------------------------------------

def test_scan_does_not_pick_up_integration_backups_as_module(tmp_path):
    """scan_and_integrate_new_modules walks modules/ for module
    directories. Anything dotted (item.startswith('.')) is skipped at
    module_stitcher.py:~171, so .integration_backups/ must never appear
    as a candidate module even if it contains subdirectories that
    superficially look module-shaped.

    This guards against a future maintainer removing the dotted-dir
    filter and reintroducing the INT-C2 confusion.
    """
    stitcher = _bare_stitcher(tmp_path)

    # _has_area_files looks for areaId+areaName+locations in JSON.
    # Seed a realistic-enough area JSON in both spots.
    area_json = (
        '{"areaId": "HH001", "areaName": "Test Area", "locations": []}'
    )

    # Create the integration backups dir with a sub-entry that has area
    # files -- if the dotted-dir filter regressed, _has_area_files would
    # return True and this would surface as a "detected module".
    backups_root = os.path.join(stitcher.modules_dir, ".integration_backups")
    fake_module_inside_backups = os.path.join(backups_root, "FakeModule_20260522")
    os.makedirs(os.path.join(fake_module_inside_backups, "areas"), exist_ok=True)
    with open(os.path.join(fake_module_inside_backups, "areas", "HH001.json"),
              "w", encoding="utf-8") as fh:
        fh.write(area_json)

    # Also seed a legitimate module so the scanner has something real
    # to return -- proving the scan is functional and our assertion
    # below is meaningful.
    real_module = "RealModule"
    real_path = os.path.join(stitcher.modules_dir, real_module)
    os.makedirs(os.path.join(real_path, "areas"), exist_ok=True)
    with open(os.path.join(real_path, "areas", "HH001.json"),
              "w", encoding="utf-8") as fh:
        fh.write(area_json)

    # Use the discovery helper directly. We don't want to invoke
    # integrate_module here -- only the detection phase.
    # `scan_and_integrate_new_modules` calls `detect_new_modules`
    # internally; we invoke the detection method directly.
    detected = stitcher.detect_new_modules()

    assert real_module in detected, (
        "Sanity check failed: legitimate module was not detected. "
        f"detected={detected}"
    )
    assert ".integration_backups" not in detected, (
        ".integration_backups was returned as a module candidate -- "
        "dotted-directory filter at module_stitcher.py:~171 has regressed."
    )
    # Belt and suspenders -- no item starting with '.' should be present.
    dotted = [d for d in detected if d.startswith(".")]
    assert dotted == [], (
        f"No dotted-name entries should be returned by _detect_new_modules. "
        f"Found: {dotted}"
    )


# ---------------------------------------------------------------------------
# Test 3: successful integration deletes the backup directory
# ---------------------------------------------------------------------------

def test_integrate_module_cleans_up_backup_on_success(tmp_path):
    """At the end of a successful integrate_module call, the backup
    created at the start is no longer needed -- the world_registry has
    been committed and rollback is no longer meaningful. The backup
    directory must be removed.

    Without cleanup, modules/.integration_backups/ grows unbounded over
    many integration runs.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "CleanupModule"
    _seed_minimal_module(stitcher.modules_dir, module_name)

    # Pre-create a fake backup so we can observe it being removed.
    # We do this by mocking _create_module_backup to return a real path
    # we control. This isolates the test to the cleanup behavior, not
    # the creation behavior (covered by test 1).
    backups_root = os.path.join(stitcher.modules_dir, ".integration_backups")
    fake_backup = os.path.join(backups_root, f"{module_name}_20260522_000000")
    os.makedirs(fake_backup, exist_ok=True)
    with open(os.path.join(fake_backup, "marker.json"), "w", encoding="utf-8") as fh:
        fh.write("{}")
    assert os.path.exists(fake_backup), "Sanity: seeded backup must exist."

    module_data = {
        "themes": [],
        "plotObjective": "",
        "levelRange": {"min": 1, "max": 1},
        "areas": {"AA001": {"areaId": "AA001"}},
        "travelNarration": {},
    }

    with mock.patch.object(stitcher, "_create_module_backup",
                            return_value=fake_backup), \
         mock.patch.object(stitcher, "analyze_module",
                            return_value=module_data), \
         mock.patch.object(stitcher, "_resolve_id_conflicts", return_value=0), \
         mock.patch.object(stitcher, "_validate_module_safety", return_value=True), \
         mock.patch.object(ms_module, "safe_write_json", return_value=True):
        result = stitcher.integrate_module(module_name)

    assert result is True, "integrate_module should succeed in this scenario."
    assert not os.path.exists(fake_backup), (
        f"Backup directory was NOT cleaned up after a successful integrate_module. "
        f"Path still present: {fake_backup}. "
        f"Wire `_cleanup_backup(backup_dir)` just before `return True`."
    )


# ---------------------------------------------------------------------------
# Test 4: _cleanup_backup is idempotent (safe when path is missing)
# ---------------------------------------------------------------------------

def test_cleanup_backup_is_idempotent_when_path_missing(tmp_path):
    """`_cleanup_backup` must be safe to call multiple times, including
    when the backup directory no longer exists or was never created.

    T3-5 will wire this same helper into the rollback path; that path
    may legitimately call cleanup after the backup has already been
    consumed/removed. The helper must not raise.
    """
    stitcher = _bare_stitcher(tmp_path)

    nonexistent = os.path.join(stitcher.modules_dir,
                                ".integration_backups",
                                "DoesNotExist_19990101_000000")
    assert not os.path.exists(nonexistent), "Sanity: target must not exist."

    # No raise on missing path.
    stitcher._cleanup_backup(nonexistent)

    # No raise on empty/None.
    stitcher._cleanup_backup("")
    stitcher._cleanup_backup(None)

    # Now seed a real backup and confirm cleanup removes it,
    # and a SECOND call (path now gone) is also a no-op.
    real_backup = os.path.join(stitcher.modules_dir,
                                ".integration_backups",
                                "Real_20260522_000000")
    os.makedirs(real_backup, exist_ok=True)
    with open(os.path.join(real_backup, "x.json"), "w", encoding="utf-8") as fh:
        fh.write("{}")
    assert os.path.exists(real_backup)

    stitcher._cleanup_backup(real_backup)
    assert not os.path.exists(real_backup), (
        "_cleanup_backup must remove the directory on first call."
    )

    # Second call -- still safe.
    stitcher._cleanup_backup(real_backup)
    assert not os.path.exists(real_backup), (
        "_cleanup_backup must remain a no-op when called again after removal."
    )
