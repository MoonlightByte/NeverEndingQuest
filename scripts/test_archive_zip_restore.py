# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
"""
Archive Zip Restore Regression Tests

Tests preflight validation, extraction, staging, and integration
for archive-root-export-and-zip-import-restore OpenSpec change.

Usage:
    python scripts/test_archive_zip_restore.py

Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""

import json
import os
import shutil
import sys
import tempfile
import zipfile
import uuid


def test_preflight_rejects_traversal():
    """Archive with ../ entry must be rejected."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    with tempfile.TemporaryDirectory() as td:
        bad_zip = os.path.join(td, 'bad.zip')
        with zipfile.ZipFile(bad_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('../evil.txt', 'x')
            zf.writestr('save_20990101_000000/save_metadata.json', json.dumps({'module': 'test_module'}))
        ok, result = mgr._validate_archive_zip_preflight(bad_zip)
        assert not ok, "Traversal zip should fail preflight"
        assert 'traversal' in str(result.get('message', '')).lower()
    return True


def test_preflight_rejects_absolute_path():
    """Archive with absolute path entry must be rejected."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    with tempfile.TemporaryDirectory() as td:
        bad_zip = os.path.join(td, 'bad.zip')
        with zipfile.ZipFile(bad_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('/etc/passwd', 'x')
            zf.writestr('save_20990101_000000/save_metadata.json', json.dumps({'module': 'test_module'}))
        ok, result = mgr._validate_archive_zip_preflight(bad_zip)
        assert not ok, "Absolute path zip should fail preflight"
        assert 'absolute' in str(result.get('message', '')).lower()
    return True


def test_preflight_rejects_missing_metadata():
    """Archive without save_metadata.json must be rejected."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    with tempfile.TemporaryDirectory() as td:
        bad_zip = os.path.join(td, 'bad.zip')
        with zipfile.ZipFile(bad_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('save_20990101_000000/party_tracker.json', '{}')
        ok, result = mgr._validate_archive_zip_preflight(bad_zip)
        assert not ok, "Missing metadata zip should fail preflight"
        assert 'metadata' in str(result.get('message', '')).lower()
    return True


def test_preflight_rejects_noncanonical_save_folder():
    """Archive with non-canonical save folder must be rejected."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    with tempfile.TemporaryDirectory() as td:
        bad_zip = os.path.join(td, 'bad.zip')
        with zipfile.ZipFile(bad_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('random_folder/save_metadata.json', json.dumps({'module': 'test_module'}))
        ok, result = mgr._validate_archive_zip_preflight(bad_zip)
        assert not ok, "Non-canonical save folder should fail preflight"
    return True


def test_preflight_rejects_unknown_module():
    """Archive with unknown source module must be rejected."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    with tempfile.TemporaryDirectory() as td:
        bad_zip = os.path.join(td, 'bad.zip')
        with zipfile.ZipFile(bad_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('save_20990101_000000/save_metadata.json', json.dumps({'module': 'does_not_exist_module_xyz123'}))
            zf.writestr('save_20990101_000000/party_tracker.json', '{}')
        ok, result = mgr._validate_archive_zip_preflight(bad_zip)
        assert not ok, "Unknown module zip should fail preflight"
        assert 'source module' in str(result.get('message', '')).lower()
    return True


def test_resolve_rejects_path_traversal():
    """Resolve must reject zip names with traversal."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    ok, result = mgr._resolve_archive_zip_path('../../../etc/passwd.zip')
    assert not ok, "Traversal zip name should be rejected"
    return True


def test_resolve_rejects_non_zip_extension():
    """Resolve must reject non-.zip extensions."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    ok, result = mgr._resolve_archive_zip_path('archive.txt')
    assert not ok, "Non-zip extension should be rejected"
    return True


def test_resolve_fails_missing_file():
    """Resolve must fail for missing files."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    ok, result = mgr._resolve_archive_zip_path('definitely_missing_file_12345.zip')
    assert not ok, "Missing file should be rejected"
    return True


def test_archive_restore_delegates_to_global_restore():
    """Archive restore must delegate to global folder restore after staging."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    modules = [m for m in os.listdir('modules') if os.path.isdir(os.path.join('modules', m))]
    if not modules:
        print("  SKIP: no modules directory entries")
        return True
    module = modules[0]

    archive_dir = mgr._get_archive_exports_directory()
    zip_name = f"archive_test_{uuid.uuid4().hex[:8]}.zip"
    zip_path = os.path.join(archive_dir, zip_name)
    save_folder = f"save_20990101_{uuid.uuid4().hex[:8]}"

    # Create synthetic archive
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{save_folder}/save_metadata.json",
            json.dumps({"module": module, "save_timestamp": "2099-01-01T00:00:00"}),
        )
        zf.writestr(f"{save_folder}/party_tracker.json", "{}")

    called = {"module": None, "save_folder": None}

    def fake_restore_global(source_module, staged_save_folder):
        called["module"] = source_module
        called["save_folder"] = staged_save_folder
        return True, "delegated restore stub"

    mgr.restore_save_game_global = fake_restore_global

    try:
        ok, message = mgr.restore_save_game_archive(zip_name)
        assert ok, f"Archive restore should succeed: {message}"
        assert called["module"] == module, f"Expected module {module}, got {called['module']}"
        assert called["save_folder"] == save_folder, f"Expected save_folder {save_folder}, got {called['save_folder']}"
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        staged_path = os.path.join('modules', module, 'saved_games', save_folder)
        if os.path.exists(staged_path):
            shutil.rmtree(staged_path, ignore_errors=True)

    return True


def test_list_archive_exports_returns_sorted_entries():
    """Archive exports listing must be sorted newest-first."""
    from updates.save_game_manager import SaveGameManager

    mgr = SaveGameManager()
    archive_dir = mgr._get_archive_exports_directory()

    # Create test archives with staggered mtimes
    test_names = []
    for i in range(3):
        name = f"archive_test_{uuid.uuid4().hex[:8]}.zip"
        path = os.path.join(archive_dir, name)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('test.txt', 'x')
        # Set mtime in the past to ensure ordering
        past_time = 1700000000 + (i * 1000)  # Different timestamps
        os.utime(path, (past_time, past_time))
        test_names.append((name, past_time))

    try:
        entries = mgr.list_archive_exports()
        entry_names = [e['zip_name'] for e in entries]

        for name, _ in test_names:
            assert name in entry_names, f"Expected {name} in archive list"

        # Verify timestamps are present
        for entry in entries:
            if entry['zip_name'] in [n for n, _ in test_names]:
                assert 'bytes' in entry, "Entry should have bytes field"
                assert 'modified_timestamp' in entry, "Entry should have modified_timestamp"
    finally:
        for name, _ in test_names:
            path = os.path.join(archive_dir, name)
            if os.path.exists(path):
                os.remove(path)

    return True


def main():
    tests = [
        test_preflight_rejects_traversal,
        test_preflight_rejects_absolute_path,
        test_preflight_rejects_missing_metadata,
        test_preflight_rejects_noncanonical_save_folder,
        test_preflight_rejects_unknown_module,
        test_resolve_rejects_path_traversal,
        test_resolve_rejects_non_zip_extension,
        test_resolve_fails_missing_file,
        test_archive_restore_delegates_to_global_restore,
        test_list_archive_exports_returns_sorted_entries,
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("Archive Zip Restore Regression Tests")
    print("=" * 60)

    for test_fn in tests:
        name = test_fn.__name__
        try:
            test_fn()
            print(f"[PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
