"""Tests for T3-5 (INT-C3): integrate_module rolls back partial mutations
on failure, covering BOTH the safety-check-fail path AND the
mid-mutation exception path.

Background:
  Pre-T3-5, `integrate_module` could leave mutated module state on disk
  when:

    PATH A: `_validate_module_safety` (which calls
            `_ai_validate_content_safety`) returns False AFTER
            `_resolve_id_conflicts` has already renamed files and
            updated area IDs.

    PATH B: Any helper raises mid-mutation (e.g. an I/O error inside
            `_resolve_id_conflicts` or `_update_all_location_references`)
            and is caught by the outer `except Exception` in
            `integrate_module`.

  In both cases the module directory on disk was a Frankenstein of
  partially-rewritten files. There was no rollback. Subsequent loads
  would see inconsistent IDs and either crash or behave unpredictably.

T3-5 fix:
  - Track a `mutations_applied` flag inside `integrate_module`. It is
    set True once `_resolve_id_conflicts` / `_update_all_location_references`
    have run. Failures BEFORE that point (e.g. analyze_module returning
    None) do not need rollback because nothing was changed.

  - On either failure path, if `mutations_applied` is True, call the
    new `_rollback_module(module_name, backup_dir)` helper. This wipes
    the current module directory and copies the backup back into place.

  - If rollback succeeds, the backup is cleaned up via the existing
    `_cleanup_backup` helper (added in T3-4).

  - If rollback FAILS (e.g. disk full, permissions error), the backup
    is RETAINED for forensics and a `.corrupted` sentinel file is
    written into the module dir so subsequent runs/operators see the
    module is in a broken half-restored state.

These tests verify all four scenarios:
  1. PATH A: safety check fails after mutations -> rollback + cleanup.
  2. PATH B: helper raises mid-mutation -> rollback + cleanup.
  3. Rollback itself fails -> .corrupted sentinel + backup retained.
  4. Pre-mutation failure -> no rollback attempted, no sentinel.
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
    """Allocate a ModuleStitcher without running __init__ (which would
    construct a real OpenAI client and touch the filesystem).
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


def _seed_module_with_areas(modules_dir: str, module_name: str,
                             area_id: str = "AA001",
                             marker: str = "pre") -> str:
    """Create a module on disk with a module JSON and an area JSON.
    The `marker` lets us distinguish original content from mutated
    content when verifying rollback restored the original state.
    """
    module_path = os.path.join(modules_dir, module_name)
    os.makedirs(os.path.join(module_path, "areas"), exist_ok=True)

    with open(os.path.join(module_path, f"{module_name}_module.json"),
              "w", encoding="utf-8") as fh:
        fh.write('{"moduleName": "%s", "marker": "%s"}' % (module_name, marker))

    with open(os.path.join(module_path, "areas", f"{area_id}.json"),
              "w", encoding="utf-8") as fh:
        fh.write(
            '{"areaId": "%s", "areaName": "Area", "locations": [], "marker": "%s"}'
            % (area_id, marker)
        )
    return module_path


def _read_marker(path: str) -> str:
    """Read the 'marker' field from a JSON file -- helper for rollback
    verification. Returns an empty string if the file is missing.
    """
    import json
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh).get("marker", "")
        except Exception:
            return ""


def _make_real_backup(stitcher: ModuleStitcher, module_name: str,
                      area_id: str = "AA001") -> str:
    """Create a real backup using the production _create_module_backup
    helper. This guarantees the test fixtures use the
    modules/.integration_backups/ path established in T3-4, not the
    legacy in-module location.
    """
    backup_dir = stitcher._create_module_backup(module_name)
    assert backup_dir, "Sanity: backup creation must produce a directory."
    # Confirm the backup is under modules/.integration_backups/ -- this
    # is the contract from T3-4 that T3-5 must continue to honour.
    backups_root = os.path.realpath(
        os.path.join(stitcher.modules_dir, ".integration_backups")
    )
    assert os.path.realpath(os.path.dirname(backup_dir)) == backups_root, (
        f"Test fixture must use the T3-4 backup location "
        f"({backups_root}); got parent "
        f"{os.path.realpath(os.path.dirname(backup_dir))}"
    )
    return backup_dir


# ---------------------------------------------------------------------------
# Test 1: PATH A -- safety check fails AFTER mutations -> rollback
# ---------------------------------------------------------------------------

def test_safety_check_failure_after_mutations_triggers_rollback(tmp_path):
    """Scenario: `_resolve_id_conflicts` has already renamed area files
    and mutated content. Then `_validate_module_safety` returns False.
    `integrate_module` MUST rollback the module from the backup, clean
    up the backup, and NOT update the world_registry.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "PathAModule"
    module_path = _seed_module_with_areas(stitcher.modules_dir, module_name,
                                          marker="pre")

    # Snapshot the file we expect to be restored.
    module_json_path = os.path.join(module_path,
                                     f"{module_name}_module.json")
    area_json_path = os.path.join(module_path, "areas", "AA001.json")
    assert _read_marker(module_json_path) == "pre"
    assert _read_marker(area_json_path) == "pre"

    # _resolve_id_conflicts: simulate a real mutation by rewriting the
    # files with a 'post' marker. We do NOT actually need to rename
    # anything -- just demonstrate that files were touched.
    def _mutating_resolver(module_name, module_data, backup_dir):
        with open(module_json_path, "w", encoding="utf-8") as fh:
            fh.write('{"moduleName": "%s", "marker": "post"}' % module_name)
        with open(area_json_path, "w", encoding="utf-8") as fh:
            fh.write(
                '{"areaId": "AA001", "areaName": "Area", "locations": [], "marker": "post"}'
            )
        return 1  # one conflict resolved

    module_data = {
        "themes": [],
        "plotObjective": "",
        "levelRange": {"min": 1, "max": 1},
        "areas": {"AA001": {"areaId": "AA001"}},
        "travelNarration": {},
    }

    # Track world_registry writes so we can assert it was NOT committed.
    write_calls = []
    def _track_write(path, payload):
        write_calls.append((path, payload))
        return True

    with mock.patch.object(stitcher, "analyze_module",
                            return_value=module_data), \
         mock.patch.object(stitcher, "_resolve_id_conflicts",
                            side_effect=_mutating_resolver), \
         mock.patch.object(stitcher,
                            "_update_bu_files_after_conflict_resolution",
                            return_value=0), \
         mock.patch.object(stitcher, "_validate_module_safety",
                            return_value=False), \
         mock.patch.object(ms_module, "safe_write_json",
                            side_effect=_track_write):
        result = stitcher.integrate_module(module_name)

    assert result is False, (
        "integrate_module must return False when safety validation fails."
    )

    # Module files must be restored to the 'pre' marker.
    assert _read_marker(module_json_path) == "pre", (
        "Module file was NOT rolled back after safety-check failure. "
        f"marker={_read_marker(module_json_path)!r} expected 'pre'."
    )
    assert _read_marker(area_json_path) == "pre", (
        "Area file was NOT rolled back after safety-check failure. "
        f"marker={_read_marker(area_json_path)!r} expected 'pre'."
    )

    # world_registry must NOT have been written.
    assert write_calls == [], (
        "world_registry was committed despite safety failure. "
        "Rollback must not update the registry. "
        f"calls={write_calls!r}"
    )

    # Module must NOT be in the in-memory registry either.
    assert module_name not in stitcher.world_registry.get("modules", {}), (
        "Module was added to in-memory registry despite safety failure."
    )

    # Backup must have been cleaned up after a successful rollback.
    backups_root = os.path.join(stitcher.modules_dir, ".integration_backups")
    if os.path.exists(backups_root):
        leftovers = [d for d in os.listdir(backups_root)
                     if d.startswith(module_name + "_")]
        assert leftovers == [], (
            f"Backup for {module_name} was not cleaned up after successful "
            f"rollback. Leftover entries: {leftovers}"
        )

    # No .corrupted sentinel on a successful rollback.
    sentinel = os.path.join(module_path, ".corrupted")
    assert not os.path.exists(sentinel), (
        ".corrupted sentinel must NOT be written when rollback succeeds."
    )


# ---------------------------------------------------------------------------
# Test 2: PATH B -- helper raises mid-mutation -> outer except rolls back
# ---------------------------------------------------------------------------

def test_mid_mutation_exception_triggers_rollback(tmp_path):
    """Scenario: `_resolve_id_conflicts` raises AFTER mutating some
    files. The outer `except Exception` in `integrate_module` catches
    it and MUST trigger rollback, restoring the original files.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "PathBModule"
    module_path = _seed_module_with_areas(stitcher.modules_dir, module_name,
                                          marker="pre")

    module_json_path = os.path.join(module_path,
                                     f"{module_name}_module.json")
    area_json_path = os.path.join(module_path, "areas", "AA001.json")

    # A partial mutation: rewrite the area file, THEN raise.
    def _half_mutate_then_raise(module_name, module_data, backup_dir):
        with open(area_json_path, "w", encoding="utf-8") as fh:
            fh.write(
                '{"areaId": "AA001", "areaName": "Area", "locations": [], "marker": "post"}'
            )
        raise RuntimeError("simulated mid-mutation explosion")

    module_data = {
        "themes": [],
        "plotObjective": "",
        "levelRange": {"min": 1, "max": 1},
        "areas": {"AA001": {"areaId": "AA001"}},
        "travelNarration": {},
    }

    write_calls = []
    def _track_write(path, payload):
        write_calls.append((path, payload))
        return True

    with mock.patch.object(stitcher, "analyze_module",
                            return_value=module_data), \
         mock.patch.object(stitcher, "_resolve_id_conflicts",
                            side_effect=_half_mutate_then_raise), \
         mock.patch.object(stitcher,
                            "_update_bu_files_after_conflict_resolution",
                            return_value=0), \
         mock.patch.object(stitcher, "_validate_module_safety",
                            return_value=True), \
         mock.patch.object(ms_module, "safe_write_json",
                            side_effect=_track_write):
        result = stitcher.integrate_module(module_name)

    assert result is False, (
        "integrate_module must return False after a mid-mutation exception."
    )

    # The area file was mutated then must be restored.
    assert _read_marker(area_json_path) == "pre", (
        "Area file was NOT rolled back after mid-mutation exception. "
        f"marker={_read_marker(area_json_path)!r} expected 'pre'."
    )
    assert _read_marker(module_json_path) == "pre", (
        "Module file marker corrupted after rollback; "
        f"marker={_read_marker(module_json_path)!r} expected 'pre'."
    )

    assert write_calls == [], (
        "world_registry must not be written during a mid-mutation crash."
    )

    backups_root = os.path.join(stitcher.modules_dir, ".integration_backups")
    if os.path.exists(backups_root):
        leftovers = [d for d in os.listdir(backups_root)
                     if d.startswith(module_name + "_")]
        assert leftovers == [], (
            f"Backup for {module_name} was not cleaned up after rollback. "
            f"Leftover entries: {leftovers}"
        )

    sentinel = os.path.join(module_path, ".corrupted")
    assert not os.path.exists(sentinel), (
        ".corrupted sentinel must NOT be written when rollback succeeds."
    )


# ---------------------------------------------------------------------------
# Test 3: rollback itself fails -> .corrupted sentinel + backup retained
# ---------------------------------------------------------------------------

def test_rollback_failure_writes_sentinel_and_retains_backup(tmp_path):
    """Scenario: safety check fails after mutations, but the rollback
    helper itself returns False (e.g. disk error). In that case:
      - integrate_module still returns False.
      - A `.corrupted` sentinel is written into the module directory
        so subsequent runs/operators see the module is broken.
      - The backup is RETAINED (not cleaned up) so a human/forensics
        process can recover the original files.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "RollbackFailModule"
    module_path = _seed_module_with_areas(stitcher.modules_dir, module_name,
                                          marker="pre")

    # Mutate so mutations_applied flips True.
    def _mutating_resolver(module_name, module_data, backup_dir):
        module_json_path = os.path.join(module_path,
                                         f"{module_name}_module.json")
        with open(module_json_path, "w", encoding="utf-8") as fh:
            fh.write('{"moduleName": "%s", "marker": "post"}' % module_name)
        return 1

    module_data = {
        "themes": [],
        "plotObjective": "",
        "levelRange": {"min": 1, "max": 1},
        "areas": {"AA001": {"areaId": "AA001"}},
        "travelNarration": {},
    }

    with mock.patch.object(stitcher, "analyze_module",
                            return_value=module_data), \
         mock.patch.object(stitcher, "_resolve_id_conflicts",
                            side_effect=_mutating_resolver), \
         mock.patch.object(stitcher,
                            "_update_bu_files_after_conflict_resolution",
                            return_value=0), \
         mock.patch.object(stitcher, "_validate_module_safety",
                            return_value=False), \
         mock.patch.object(stitcher, "_rollback_module",
                            return_value=False), \
         mock.patch.object(ms_module, "safe_write_json", return_value=True):
        result = stitcher.integrate_module(module_name)

    assert result is False

    # Sentinel must be written inside the module dir.
    sentinel = os.path.join(module_path, ".corrupted")
    assert os.path.exists(sentinel), (
        f".corrupted sentinel was NOT written when rollback failed. "
        f"Expected: {sentinel}"
    )

    # Backup must be RETAINED (not cleaned up) for forensics.
    backups_root = os.path.join(stitcher.modules_dir, ".integration_backups")
    assert os.path.isdir(backups_root), (
        f".integration_backups root was removed when rollback failed; "
        f"the backup must be retained for forensics."
    )
    leftovers = [d for d in os.listdir(backups_root)
                 if d.startswith(module_name + "_")]
    assert leftovers, (
        f"Backup for {module_name} was cleaned up despite rollback failure. "
        f"Rollback failure path must RETAIN the backup for forensics. "
        f".integration_backups contents: {os.listdir(backups_root)}"
    )


# ---------------------------------------------------------------------------
# Test 4: failure BEFORE mutations -> no rollback, no sentinel
# ---------------------------------------------------------------------------

def test_pre_mutation_failure_does_not_rollback(tmp_path):
    """Backward-compat: when integration fails BEFORE any mutation
    occurs (e.g. analyze_module returns None), there is nothing to
    roll back. The rollback helper must NOT be invoked, and no
    .corrupted sentinel should be written. This guards against the
    new mutations_applied flag accidentally firing in the wrong cases.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "EarlyFailModule"
    module_path = _seed_module_with_areas(stitcher.modules_dir, module_name,
                                          marker="pre")

    module_json_path = os.path.join(module_path,
                                     f"{module_name}_module.json")

    # analyze_module returns None -> integrate_module bails before
    # _resolve_id_conflicts is ever called.
    with mock.patch.object(stitcher, "analyze_module", return_value=None), \
         mock.patch.object(stitcher, "_rollback_module") as rollback_mock, \
         mock.patch.object(ms_module, "safe_write_json", return_value=True):
        result = stitcher.integrate_module(module_name)

    assert result is False, (
        "integrate_module must return False when analyze_module returns None."
    )

    # Rollback must NOT have been called -- there were no mutations.
    rollback_mock.assert_not_called()

    # No .corrupted sentinel.
    sentinel = os.path.join(module_path, ".corrupted")
    assert not os.path.exists(sentinel), (
        ".corrupted sentinel must NOT be written when integration failed "
        "before any mutation occurred."
    )

    # Original file content is intact.
    assert _read_marker(module_json_path) == "pre", (
        "Original module file should be unchanged after a pre-mutation "
        f"failure; marker={_read_marker(module_json_path)!r}"
    )

    # Backup may exist or not (we don't mandate _create_module_backup
    # didn't run), but if it does exist it should also be cleaned up so
    # the failure path doesn't leak. Either no .integration_backups
    # directory, or no entries for this module.
    backups_root = os.path.join(stitcher.modules_dir, ".integration_backups")
    if os.path.isdir(backups_root):
        leftovers = [d for d in os.listdir(backups_root)
                     if d.startswith(module_name + "_")]
        assert leftovers == [], (
            f"Pre-mutation failure leaked a backup for {module_name}: "
            f"{leftovers}"
        )


# ---------------------------------------------------------------------------
# Test 5 (unit test for the helper itself): _rollback_module restores
# from a real backup created by _create_module_backup. This is the
# direct unit test that makes sure the helper actually works end-to-end
# against the T3-4 backup location, independent of integrate_module's
# wiring.
# ---------------------------------------------------------------------------

def test_rollback_module_restores_from_real_backup(tmp_path):
    """Unit test for the new helper: create a real backup via the T3-4
    helper, mutate the module on disk, then call _rollback_module and
    confirm the original state is restored byte-for-byte from the
    backup at modules/.integration_backups/.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "UnitRollbackModule"
    module_path = _seed_module_with_areas(stitcher.modules_dir, module_name,
                                          marker="pre")

    backup_dir = _make_real_backup(stitcher, module_name)

    # Mutate the live module dir: replace one file's marker.
    area_json_path = os.path.join(module_path, "areas", "AA001.json")
    with open(area_json_path, "w", encoding="utf-8") as fh:
        fh.write(
            '{"areaId": "AA001", "areaName": "Area", "locations": [], "marker": "post"}'
        )
    # Also add a stray file that was not in the backup -- rollback
    # should remove it (because rollback wipes the module dir).
    stray = os.path.join(module_path, "stray_file.json")
    with open(stray, "w", encoding="utf-8") as fh:
        fh.write("{}")

    assert _read_marker(area_json_path) == "post"
    assert os.path.exists(stray)

    ok = stitcher._rollback_module(module_name, backup_dir)
    assert ok is True, "Rollback helper must return True on success."

    # Original content restored.
    assert _read_marker(area_json_path) == "pre", (
        "Rollback did not restore area file to its pre-mutation state. "
        f"marker={_read_marker(area_json_path)!r}"
    )
    # Stray file removed (it was not in the backup).
    assert not os.path.exists(stray), (
        "Rollback should have wiped files that were not present in the "
        "backup, but stray_file.json is still present."
    )


def test_rollback_preserves_media_and_saved_games(tmp_path):
    """INT-C3 regression: files that existed at backup time in non-JSON
    locations (media/, saved_games/) and root .md files must SURVIVE a
    rollback. The pre-fix backup only saved root *.json plus a fixed
    subdir list, so rollback (which rmtree's the whole module dir)
    permanently destroyed generated media and save files. The backup now
    captures the full module tree, so rollback restores them.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "MediaRollbackModule"
    module_path = _seed_module_with_areas(stitcher.modules_dir, module_name,
                                          marker="pre")

    # Seed expensive/non-JSON artifacts that exist BEFORE the backup.
    media_dir = os.path.join(module_path, "media", "monsters")
    os.makedirs(media_dir, exist_ok=True)
    media_file = os.path.join(media_dir, "goblin.jpg")
    with open(media_file, "wb") as fh:
        fh.write(b"\xff\xd8\xff\xe0JFIF-fake-image-bytes")

    saves_dir = os.path.join(module_path, "saved_games")
    os.makedirs(saves_dir, exist_ok=True)
    save_file = os.path.join(saves_dir, "save_001.json")
    with open(save_file, "w", encoding="utf-8") as fh:
        fh.write('{"slot": 1, "marker": "pre"}')

    summary_md = os.path.join(module_path, "MODULE_SUMMARY.md")
    with open(summary_md, "w", encoding="utf-8") as fh:
        fh.write("# Summary\nmarker: pre\n")

    # Back up the full tree, then mutate/destroy the live copies.
    backup_dir = _make_real_backup(stitcher, module_name)
    os.remove(media_file)
    os.remove(save_file)
    with open(summary_md, "w", encoding="utf-8") as fh:
        fh.write("# Summary\nmarker: post\n")

    ok = stitcher._rollback_module(module_name, backup_dir)
    assert ok is True, "Rollback helper must return True on success."

    # All three artifact classes must be restored from the backup.
    assert os.path.exists(media_file), (
        "INT-C3: media/ file was not restored on rollback -- backup did "
        "not capture the full module tree."
    )
    with open(media_file, "rb") as fh:
        assert fh.read() == b"\xff\xd8\xff\xe0JFIF-fake-image-bytes"

    assert os.path.exists(save_file), (
        "INT-C3: saved_games/ file was not restored on rollback."
    )
    assert _read_marker(save_file) == "pre"

    assert os.path.exists(summary_md), (
        "INT-C3: root .md file was not restored on rollback."
    )
    with open(summary_md, "r", encoding="utf-8") as fh:
        assert "marker: pre" in fh.read()


def test_rollback_module_returns_false_when_backup_missing(tmp_path):
    """`_rollback_module` must return False (and not raise) when the
    backup path is missing or empty. This is what triggers the
    .corrupted sentinel branch in integrate_module.
    """
    stitcher = _bare_stitcher(tmp_path)
    module_name = "NoBackupModule"
    _seed_module_with_areas(stitcher.modules_dir, module_name, marker="pre")

    # Missing path.
    assert stitcher._rollback_module(module_name,
        os.path.join(stitcher.modules_dir, ".integration_backups",
                     "does_not_exist")) is False

    # Empty / None path.
    assert stitcher._rollback_module(module_name, "") is False
    assert stitcher._rollback_module(module_name, None) is False
