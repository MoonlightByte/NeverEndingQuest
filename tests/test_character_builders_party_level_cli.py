"""
Tests for T5-2 (CH-C1, CH-M3): party_level must be passed via CLI from
combat_builder to monster_builder / npc_builder subprocesses.

Current bugs:
- core/generators/combat_builder.py:153 invokes monster_builder.py as a
  subprocess with ONLY the monster name. monster_builder.py reads
  party_tracker.json itself; if that read fails (file lock, parse error),
  a bare `except:` clause falls back to party_level = 1. A level 8 party
  silently gets CR 1/8 monsters.

- core/generators/combat_builder.py:241 invokes npc_builder.py similarly.
  npc_builder.py:131 defaults level_guidance to "1-3" when no level is
  passed, regardless of the actual party's level.

Fix: combat_builder must pass `--party-level <N>` on the subprocess
command line. monster_builder and npc_builder must accept that flag
(via argparse) and use the supplied value instead of the file-read
fallback. Backward compat: invocations without the flag must still work.
"""

import os
import sys
import json
import importlib
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import combat_builder


# ---------------------------------------------------------------------------
# Test 1: combat_builder passes --party-level to monster_builder subprocess
# ---------------------------------------------------------------------------

def test_combat_builder_passes_party_level_to_monster_builder(tmp_path, monkeypatch):
    """When combat_builder spawns monster_builder.py to create a missing
    monster, the subprocess argv MUST include `--party-level <N>` where
    N is the average party level computed from party_tracker.json.

    Pre-fix: argv is just ["python", monster_builder.py, monster_name].
    Post-fix: argv includes "--party-level" and the integer level value.
    """
    # Build an isolated working directory containing party_tracker + chars
    # representing a level 8 party (two level 8 characters).
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    (workdir / "characters").mkdir()
    (workdir / "characters" / "hero.json").write_text(json.dumps({
        "name": "Hero", "level": 8
    }))
    (workdir / "characters" / "ally.json").write_text(json.dumps({
        "name": "Ally", "level": 8
    }))
    (workdir / "party_tracker.json").write_text(json.dumps({
        "module": "TestModule",
        "partyMembers": ["hero", "ally"],
        "worldConditions": {"currentLocationId": "A01", "currentAreaId": "A01"},
    }))

    # ModulePathManager will look for the monster in a module dir that
    # does not exist, so load_or_create_monster will hit the subprocess
    # path. Use a fake monster name guaranteed not to exist on disk.
    captured = {}

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        captured["argv"] = list(argv)
        # Pretend monster_builder succeeded so combat_builder proceeds
        # to look for the created file (which it won't find -- that's
        # fine, we only care about the argv).
        return subprocess.CompletedProcess(args=argv, returncode=0,
                                           stdout="", stderr="")

    with patch.object(combat_builder.subprocess, "run", side_effect=_fake_run):
        # We don't care about the return value -- only that subprocess
        # was invoked with the new flag.
        combat_builder.load_or_create_monster("definitely_does_not_exist_xyz")

    assert "argv" in captured, "subprocess.run was never called"
    argv = captured["argv"]
    assert "--party-level" in argv, (
        f"Expected '--party-level' in monster_builder argv, got: {argv}"
    )
    idx = argv.index("--party-level")
    assert idx + 1 < len(argv), "No value after --party-level"
    assert argv[idx + 1] == "8", (
        f"Expected party level 8 in argv, got: {argv[idx + 1]!r} "
        f"(full argv: {argv})"
    )


# ---------------------------------------------------------------------------
# Test 2: combat_builder passes --party-level to npc_builder subprocess
# ---------------------------------------------------------------------------

def test_combat_builder_passes_party_level_to_npc_builder(tmp_path, monkeypatch):
    """When combat_builder spawns npc_builder.py to create a missing NPC,
    the subprocess argv MUST include `--party-level <N>` so the NPC is
    scaled appropriately. Pre-fix the flag is absent and npc_builder
    falls back to 'level 1-3' guidance regardless of party strength.
    """
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    (workdir / "characters").mkdir()
    (workdir / "characters" / "hero.json").write_text(json.dumps({
        "name": "Hero", "level": 8
    }))
    (workdir / "characters" / "ally.json").write_text(json.dumps({
        "name": "Ally", "level": 8
    }))
    (workdir / "party_tracker.json").write_text(json.dumps({
        "module": "TestModule",
        "partyMembers": ["hero", "ally"],
        "worldConditions": {"currentLocationId": "A01", "currentAreaId": "A01"},
    }))

    captured = {}

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        captured["argv"] = list(argv)
        return subprocess.CompletedProcess(args=argv, returncode=0,
                                           stdout="", stderr="")

    with patch.object(combat_builder.subprocess, "run", side_effect=_fake_run):
        combat_builder.load_or_create_npc("definitely_no_such_npc_xyz")

    assert "argv" in captured, "subprocess.run was never called"
    argv = captured["argv"]
    assert "--party-level" in argv, (
        f"Expected '--party-level' in npc_builder argv, got: {argv}"
    )
    idx = argv.index("--party-level")
    assert idx + 1 < len(argv), "No value after --party-level"
    assert argv[idx + 1] == "8", (
        f"Expected party level 8 in npc_builder argv, got: {argv[idx + 1]!r} "
        f"(full argv: {argv})"
    )


# ---------------------------------------------------------------------------
# Test 3: monster_builder.main() uses --party-level when supplied
# ---------------------------------------------------------------------------

def test_monster_builder_main_uses_explicit_party_level(tmp_path, monkeypatch):
    """When monster_builder is invoked with `--party-level 8`, the
    generate_monster() call MUST receive party_level=8 even if the
    party_tracker.json on disk would give a different value.

    This validates that the CLI flag actually overrides the fallback
    file-read path.
    """
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    # Set up a party_tracker that would yield level 1 (or no level) so
    # we can verify the CLI flag (level 8) overrides it.
    (workdir / "characters").mkdir()
    (workdir / "characters" / "weakie.json").write_text(json.dumps({
        "name": "Weakie", "level": 1
    }))
    (workdir / "party_tracker.json").write_text(json.dumps({
        "module": "TestModule",
        "partyMembers": ["weakie"],
    }))

    # Force-reload monster_builder so any module-level state is fresh.
    if "core.generators.monster_builder" in sys.modules:
        del sys.modules["core.generators.monster_builder"]
    monster_builder = importlib.import_module("core.generators.monster_builder")

    captured_levels = []

    def _fake_generate_monster(monster_name, schema, party_level=1):
        captured_levels.append(party_level)
        # Return None so main() exits via sys.exit(1) without trying to
        # save anything. We catch SystemExit below.
        return None

    monkeypatch.setattr(monster_builder, "generate_monster",
                        _fake_generate_monster)
    monkeypatch.setattr(monster_builder, "load_schema",
                        lambda _path: {"fake": "schema"})

    monkeypatch.setattr(sys, "argv",
                        ["monster_builder.py", "Goblin", "--party-level", "8"])

    with pytest.raises(SystemExit):
        monster_builder.main()

    assert captured_levels, "generate_monster was never called"
    assert captured_levels[0] == 8, (
        f"Expected party_level=8 from CLI flag, got {captured_levels[0]!r}. "
        "CLI --party-level must override the party_tracker.json fallback."
    )


# ---------------------------------------------------------------------------
# Test 4 (regression): monster_builder without --party-level still works
# ---------------------------------------------------------------------------

def test_monster_builder_main_backward_compat_without_flag(tmp_path, monkeypatch):
    """Regression test: invoking monster_builder.py with ONLY the monster
    name (no --party-level) must still work. It should fall back to the
    party_tracker.json read OR a sensible default (level 1).

    Backward compat is required because other callers (besides
    combat_builder) may still invoke monster_builder without the flag.
    """
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    # No party_tracker.json on disk -- forces the fallback path.
    if "core.generators.monster_builder" in sys.modules:
        del sys.modules["core.generators.monster_builder"]
    monster_builder = importlib.import_module("core.generators.monster_builder")

    captured_levels = []

    def _fake_generate_monster(monster_name, schema, party_level=1):
        captured_levels.append(party_level)
        return None  # forces sys.exit(1)

    monkeypatch.setattr(monster_builder, "generate_monster",
                        _fake_generate_monster)
    monkeypatch.setattr(monster_builder, "load_schema",
                        lambda _path: {"fake": "schema"})

    # No --party-level supplied -- only the monster name.
    monkeypatch.setattr(sys, "argv", ["monster_builder.py", "Goblin"])

    with pytest.raises(SystemExit):
        monster_builder.main()

    assert captured_levels, "generate_monster was never called"
    # Must be an int and a reasonable default (the legacy fallback was 1).
    assert isinstance(captured_levels[0], int), (
        f"party_level should be int, got {type(captured_levels[0]).__name__}: "
        f"{captured_levels[0]!r}"
    )
    assert captured_levels[0] >= 1, (
        f"party_level fallback should be >= 1, got {captured_levels[0]!r}"
    )
