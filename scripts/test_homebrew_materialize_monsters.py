# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""
Tests for homebrew_materialize_monsters.py
Tests dict/list compendium compatibility, auto-repair, and materialization logic.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

sys.path.insert(0, str(Path(__file__).parent))

import homebrew_materialize_monsters as hmm

from homebrew_materialize_monsters import (
    _normalize_monster_name,
    _load_monster_compendium,
    _load_monsters_seed,
    _repair_path_conflict,
    _write_monster_file,
    materialize_monsters,
)


def test_normalize_monster_name():
    """Test name normalization matches runtime combat lookup."""
    assert _normalize_monster_name("Giant Spider") == "giant_spider"
    assert _normalize_monster_name("Dragon's Servant") == "dragons_servant"
    assert _normalize_monster_name("ZOMBIE WARRIOR") == "zombie_warrior"
    assert _normalize_monster_name("  Spaces  ") == "spaces"
    assert _normalize_monster_name("") == ""
    print("[PASS] test_normalize_monster_name")


def test_dict_form_compendium():
    """Test dict-form compendium: {slug: {name: ..., ...}}"""
    with tempfile.TemporaryDirectory() as tmpdir:
        bestiary_path = Path(tmpdir) / "data" / "bestiary"
        bestiary_path.mkdir(parents=True)
        compendium_file = bestiary_path / "monster_compendium.json"

        compendium_data = {
            "monsters": {
                "giant_spider": {"name": "Giant Spider", "hitPoints": 26},
                "skeleton": {"name": "Skeleton", "hitPoints": 13},
            }
        }
        compendium_file.write_text(json.dumps(compendium_data))

        # Temporarily change working directory
        import os

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            lookup = _load_monster_compendium()
            assert "giant_spider" in lookup
            assert "skeleton" in lookup
            assert lookup["giant_spider"]["name"] == "Giant Spider"
        finally:
            os.chdir(old_cwd)

    print("[PASS] test_dict_form_compendium")


def test_list_form_compendium():
    """Test list-form compendium: [{name: ...}, ...]"""
    with tempfile.TemporaryDirectory() as tmpdir:
        bestiary_path = Path(tmpdir) / "data" / "bestiary"
        bestiary_path.mkdir(parents=True)
        compendium_file = bestiary_path / "monster_compendium.json"

        compendium_data = {
            "monsters": [
                {"name": "Giant Spider", "hitPoints": 26},
                {"name": "Skeleton", "hitPoints": 13},
            ]
        }
        compendium_file.write_text(json.dumps(compendium_data))

        import os

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            lookup = _load_monster_compendium()
            assert "giant_spider" in lookup
            assert "skeleton" in lookup
        finally:
            os.chdir(old_cwd)

    print("[PASS] test_list_form_compendium")


def test_seed_string_entries():
    """Test seed with string list entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_path = Path(tmpdir) / "modules" / "test_mod"
        module_path.mkdir(parents=True)
        seed_file = module_path / "monsters_seed.json"

        seed_data = {"monsters": ["Giant Spider", "Skeleton", "Zombie"]}
        seed_file.write_text(json.dumps(seed_data))

        seeds = _load_monsters_seed(module_path)
        assert len(seeds) == 3
        assert seeds[0] == "Giant Spider"
        assert seeds[1] == "Skeleton"
        assert seeds[2] == "Zombie"

    print("[PASS] test_seed_string_entries")


def test_seed_dict_entries():
    """Test seed with dict list entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_path = Path(tmpdir) / "modules" / "test_mod"
        module_path.mkdir(parents=True)
        seed_file = module_path / "monsters_seed.json"

        seed_data = {
            "monsters": [
                {"name": "Giant Spider", "quantity": 2},
                {"name": "Skeleton"},
            ]
        }
        seed_file.write_text(json.dumps(seed_data))

        seeds = _load_monsters_seed(module_path)
        assert len(seeds) == 2
        assert seeds[0]["name"] == "Giant Spider"
        assert seeds[1]["name"] == "Skeleton"

    print("[PASS] test_seed_dict_entries")


def test_path_conflict_repair():
    """Test auto-repair when target path is a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monsters_dir = Path(tmpdir) / "monsters"
        monsters_dir.mkdir()

        # Create a directory at the target path
        conflict_dir = monsters_dir / "giant_spider.json"
        conflict_dir.mkdir()
        (conflict_dir / "old_file.txt").write_text("old content")

        # Attempt repair
        repair = _repair_path_conflict(conflict_dir, dry_run=False)

        assert repair["repaired"] is True
        assert repair["conflict_path"] == str(conflict_dir)
        assert repair["archive_path"] is not None
        assert "_conflict_" in repair["archive_path"]

        # Verify original directory is gone
        assert not conflict_dir.exists()

        # Verify archive exists
        archive_path = Path(repair["archive_path"])
        assert archive_path.exists()
        assert (archive_path / "old_file.txt").read_text() == "old content"

    print("[PASS] test_path_conflict_repair")


def test_path_conflict_no_conflict():
    """Test repair when no conflict exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target_file = Path(tmpdir) / "test.json"

        # No conflict - file doesn't exist
        repair = _repair_path_conflict(target_file, dry_run=False)

        assert repair["repaired"] is False
        assert repair["conflict_path"] == str(target_file)
        assert repair["archive_path"] is None

    print("[PASS] test_path_conflict_no_conflict")


def test_write_monster_file_with_repair():
    """Test writing monster file triggers repair when conflict exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_path = Path(tmpdir)
        monsters_dir = module_path / "monsters"
        monsters_dir.mkdir()

        # Create conflicting directory
        conflict_dir = monsters_dir / "test_monster.json"
        conflict_dir.mkdir()

        monster_data = {"name": "Test Monster", "hitPoints": 10}

        result = _write_monster_file(
            module_path, "test_monster", monster_data, dry_run=False
        )

        assert result["written"] is True
        assert result["repair"] is not None
        assert result["repair"]["repaired"] is True

        # Verify file was created
        monster_file = monsters_dir / "test_monster.json"
        assert monster_file.is_file()
        saved_data = json.loads(monster_file.read_text())
        assert saved_data["name"] == "Test Monster"

    print("[PASS] test_write_monster_file_with_repair")


def test_materialize_degraded_status():
    """Test degraded status when monsters missing from bestiary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup module
        module_path = Path(tmpdir) / "modules" / "test_mod"
        module_path.mkdir(parents=True)

        # Create seed with non-existent monster
        seed_file = module_path / "monsters_seed.json"
        seed_file.write_text(json.dumps({"monsters": ["NonExistentMonster123"]}))

        # Setup minimal compendium (empty)
        bestiary_path = Path(tmpdir) / "data" / "bestiary"
        bestiary_path.mkdir(parents=True)
        compendium_file = bestiary_path / "monster_compendium.json"
        compendium_file.write_text(json.dumps({"monsters": {}}))

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            result = materialize_monsters("test_mod", strict=False, dry_run=True)

            assert result["status"] == "degraded"
            assert result["blocked_count"] == 1
            assert (
                result["blocker_classes"].get("authorized_monster_provider_unavailable")
                == 1
            )
            assert result["missing_in_bestiary_count"] == 1
            assert "NonExistentMonster123" in result["missing_names"]
            assert "note" in result
        finally:
            os.chdir(old_cwd)

    print("[PASS] test_materialize_degraded_status")


def test_materialize_strict_failure():
    """Test strict mode failure when monsters missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup module
        module_path = Path(tmpdir) / "modules" / "test_mod"
        module_path.mkdir(parents=True)

        # Create seed with non-existent monster
        seed_file = module_path / "monsters_seed.json"
        seed_file.write_text(json.dumps({"monsters": ["MissingMonster"]}))

        # Setup minimal compendium (empty)
        bestiary_path = Path(tmpdir) / "data" / "bestiary"
        bestiary_path.mkdir(parents=True)
        compendium_file = bestiary_path / "monster_compendium.json"
        compendium_file.write_text(json.dumps({"monsters": {}}))

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            result = materialize_monsters("test_mod", strict=True, dry_run=True)

            assert result["status"] == "failed"
            assert result["blocked_count"] == 1
            assert (
                result["blocker_classes"].get("authorized_monster_provider_unavailable")
                == 1
            )
            assert result["missing_in_bestiary_count"] == 1
            assert "strict mode" in result["error"].lower()
        finally:
            os.chdir(old_cwd)

    print("[PASS] test_materialize_strict_failure")


def test_materialize_no_seed_uses_authored_fallback():
    """Test authored monster refs are discovered when seed file is absent."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_path = Path(tmpdir) / "modules" / "test_mod"
        areas_dir = module_path / "areas"
        areas_dir.mkdir(parents=True)

        # No monsters_seed.json on purpose
        area_payload = {
            "areaId": "TST001",
            "areaName": "Test Area",
            "locations": [
                {
                    "locationId": "L01",
                    "name": "Ruined Hall",
                    "description": "A cracked stone hall with goblin markings.",
                    "monsters": ["Goblin"],
                }
            ],
        }
        (areas_dir / "TST001.json").write_text(
            json.dumps(area_payload), encoding="utf-8"
        )

        bestiary_path = Path(tmpdir) / "data" / "bestiary"
        bestiary_path.mkdir(parents=True)
        compendium_file = bestiary_path / "monster_compendium.json"
        compendium_file.write_text(
            json.dumps({"monsters": {"goblin": {"name": "Goblin", "hitPoints": 7}}}),
            encoding="utf-8",
        )

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            result = materialize_monsters("test_mod", strict=True, dry_run=True)

            assert result["status"] == "success"
            assert result["blocked_count"] == 0
            assert result["candidate_sources"]["seed_count"] == 0
            assert result["candidate_sources"]["authored_count"] >= 1
            assert result["candidate_sources"]["seed_missing_fallback_used"] is True
            assert result["hydration_modes"].get("bestiary", 0) >= 1
            assert any(
                str(item.get("canonical_slug")) == "goblin"
                for item in result.get("monster_results", [])
            )
        finally:
            os.chdir(old_cwd)

    print("[PASS] test_materialize_no_seed_uses_authored_fallback")


def test_materialize_precedence_mode_accounting():
    """Test deterministic mode accounting across precedence outcomes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_path = Path(tmpdir) / "modules" / "test_mod"
        module_path.mkdir(parents=True)

        # Candidate order is controlled through seed entries.
        seed_file = module_path / "monsters_seed.json"
        seed_file.write_text(
            json.dumps(
                {
                    "monsters": [
                        "Existing Monster",
                        "Reusable Monster",
                        "Bestiary Monster",
                        "Generated Monster",
                    ]
                }
            ),
            encoding="utf-8",
        )

        bestiary_path = Path(tmpdir) / "data" / "bestiary"
        bestiary_path.mkdir(parents=True)
        (bestiary_path / "monster_compendium.json").write_text(
            json.dumps({"monsters": {}}),
            encoding="utf-8",
        )

        old_materialize = hmm.materialize_authorized_monster_file

        def _fake_materialize(
            module_slug, monster_name, monster_builder_path, **kwargs
        ):
            mode_map = {
                "Existing Monster": "existing",
                "Reusable Monster": "reuse",
                "Bestiary Monster": "bestiary",
                "Generated Monster": "generated",
            }
            mode = mode_map.get(monster_name)
            if not mode:
                return {
                    "ok": False,
                    "error_class": "authorized_monster_hydration_failed",
                    "error_message": "Unexpected fixture monster",
                    "canonical_slug": _normalize_monster_name(monster_name),
                    "canonical_name": monster_name,
                }
            return {
                "ok": True,
                "source": mode,
                "canonical_slug": _normalize_monster_name(monster_name),
                "canonical_name": monster_name,
                "requested_slug": _normalize_monster_name(monster_name),
                "requested_name": monster_name,
                "bestiary_missing": mode in {"generated"},
            }

        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        hmm.materialize_authorized_monster_file = _fake_materialize
        try:
            result = materialize_monsters("test_mod", strict=False, dry_run=True)

            assert result["status"] == "success"
            assert result["blocked_count"] == 0
            assert result["hydration_modes"].get("existing") == 1
            assert result["hydration_modes"].get("reuse") == 1
            assert result["hydration_modes"].get("bestiary") == 1
            assert result["hydration_modes"].get("generated") == 1
            assert result["skipped_existing_count"] == 1
            assert result["created_count"] == 3

            modes_in_order = [
                str(item.get("mode") or "")
                for item in result.get("monster_results", [])
            ]
            assert modes_in_order[:4] == [
                "existing",
                "reuse",
                "bestiary",
                "generated",
            ]
        finally:
            hmm.materialize_authorized_monster_file = old_materialize
            os.chdir(old_cwd)

    print("[PASS] test_materialize_precedence_mode_accounting")


if __name__ == "__main__":
    test_normalize_monster_name()
    test_dict_form_compendium()
    test_list_form_compendium()
    test_seed_string_entries()
    test_seed_dict_entries()
    test_path_conflict_repair()
    test_path_conflict_no_conflict()
    test_write_monster_file_with_repair()
    test_materialize_degraded_status()
    test_materialize_strict_failure()
    test_materialize_no_seed_uses_authored_fallback()
    test_materialize_precedence_mode_accounting()

    print("\n[OK] All tests passed!")
