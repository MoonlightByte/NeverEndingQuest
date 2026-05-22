"""
Tests for T2-7 (CH-C1): Surface party_tracker read failures in
monster_builder and add subprocess return-code check in combat_builder.

Background:
- T5-2 (commit c141827) made combat_builder pass --party-level via CLI
  to the monster_builder subprocess. The legacy file-read fallback in
  monster_builder.main() now only runs when --party-level is omitted
  (e.g., a direct/legacy invocation).
- Pre-fix bug (CH-C1): When that fallback path raises (corrupt
  party_tracker.json, character file parse error, etc.), a bare
  `except:` silently sets party_level = 1. A level-8 party gets CR 1/8
  monsters with no error indication.

Fix:
- monster_builder.main(): on fallback read failure, print a clear error
  mentioning party_tracker AND exit with non-zero status.
- combat_builder.generate_encounter(): when subprocess.run for
  monster_builder returns a non-zero code, raise RuntimeError so the
  failure is visible to the caller (currently swallowed -- the parent
  just returns None and the caller has no idea why).
"""

import os
import sys
import json
import importlib
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import combat_builder


# ---------------------------------------------------------------------------
# Test 1: monster_builder exits non-zero with a clear error when the
# fallback party_tracker.json read raises (no --party-level supplied).
# ---------------------------------------------------------------------------

def test_monster_builder_surfaces_party_tracker_read_failure(tmp_path,
                                                             monkeypatch,
                                                             capsys):
    """Pre-fix: a bare `except:` swallowed any exception in the fallback
    read path and defaulted party_level to 1. Post-fix: any exception
    while reading party_tracker.json (or the character files it points
    to) must produce a non-zero exit AND a stderr message that mentions
    party_tracker so the operator can see what failed.
    """
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    # Force-reload monster_builder to pick up a fresh module state.
    if "core.generators.monster_builder" in sys.modules:
        del sys.modules["core.generators.monster_builder"]
    monster_builder = importlib.import_module("core.generators.monster_builder")

    # Patch safe_json_load INSIDE the monster_builder module's namespace
    # at import-time so the function `main()` imports inside its body
    # picks up our patched version. The simplest way: patch the source
    # symbol in utils.encoding_utils so the local `from ... import` in
    # main() resolves to our raising stub.
    from utils import encoding_utils

    def _raising_load(filepath):
        raise ValueError("simulated party_tracker.json parse failure")

    monkeypatch.setattr(encoding_utils, "safe_json_load", _raising_load)

    # No --party-level on the CLI -> falls into the file-read branch
    # which now raises -> must sys.exit(1) with a clear message.
    monkeypatch.setattr(sys, "argv", ["monster_builder.py", "Goblin"])

    with pytest.raises(SystemExit) as exc_info:
        monster_builder.main()

    # Must be a non-zero exit code.
    assert exc_info.value.code not in (0, None), (
        f"Expected non-zero exit code on party_tracker read failure, "
        f"got {exc_info.value.code!r}"
    )

    captured = capsys.readouterr()
    combined = (captured.err or "") + (captured.out or "")
    assert "party_tracker" in combined.lower(), (
        "Expected error output mentioning party_tracker so the operator "
        f"can see what failed. Got stdout={captured.out!r} "
        f"stderr={captured.err!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: combat_builder.generate_encounter raises when the
# monster_builder subprocess returns a non-zero exit code.
# ---------------------------------------------------------------------------

def test_generate_encounter_raises_on_monster_builder_nonzero_returncode(
        tmp_path, monkeypatch):
    """Pre-fix: load_or_create_monster() printed a message and returned
    None on subprocess failure; generate_encounter() saw None and just
    returned None too. The caller had no clear signal that the monster
    build had failed -- it looked indistinguishable from "no encounter
    needed".

    Post-fix: a non-zero returncode from the monster_builder subprocess
    must raise a RuntimeError (or other clear exception) that propagates
    out of generate_encounter so the caller cannot silently proceed.
    The error message must include the subprocess stderr so the operator
    can diagnose.
    """
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    # generate_encounter() loads a player file by name. Provide a
    # minimal, schema-loose player that satisfies the field accesses
    # before the monster loop runs.
    (workdir / "characters").mkdir()
    player_record = {
        "name": "Hero",
        "level": 5,
        "hitPoints": 30,
        "maxHitPoints": 30,
        "armorClass": 15,
        "status": "alive",
        "condition_affected": [],
    }
    (workdir / "characters" / "hero.json").write_text(json.dumps(player_record))
    (workdir / "party_tracker.json").write_text(json.dumps({
        "module": "TestModule",
        "partyMembers": ["hero"],
        "worldConditions": {"currentLocationId": "A01", "currentAreaId": "A01"},
    }))

    # combat_builder.load_json / ModulePathManager will look in module
    # dirs. Force a path resolution that points at our hero.json by
    # stubbing get_current_location() and load_json() to return the
    # data we just wrote.
    monkeypatch.setattr(combat_builder, "get_current_location",
                        lambda: "A01")
    monkeypatch.setattr(combat_builder, "get_next_encounter_number",
                        lambda location: 1)
    monkeypatch.setattr(combat_builder, "load_json",
                        lambda path: player_record
                        if path and "hero" in str(path).lower()
                        else None)
    monkeypatch.setattr(combat_builder, "backup_player_file",
                        lambda path: None)

    stderr_message = "BOOM: simulated monster_builder failure"

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        return subprocess.CompletedProcess(
            args=argv, returncode=1, stdout="", stderr=stderr_message,
        )

    # Encounter with a monster guaranteed not to exist on disk so
    # load_or_create_monster() hits the subprocess path.
    encounter_data = {
        "player": "hero",
        "encounterSummary": "Test encounter",
        "monsters": ["definitely_no_such_monster_xyz"],
        "npcs": [],
    }

    with patch.object(combat_builder.subprocess, "run", side_effect=_fake_run):
        with pytest.raises(Exception) as exc_info:
            combat_builder.generate_encounter(encounter_data)

    # The exception must be a RuntimeError (or subclass) -- NOT
    # SystemExit and NOT a bare AttributeError from None being treated
    # as a dict. The message should reference the failure clearly.
    assert isinstance(exc_info.value, RuntimeError), (
        f"Expected RuntimeError on monster_builder subprocess failure, "
        f"got {type(exc_info.value).__name__}: {exc_info.value!r}"
    )
    msg = str(exc_info.value)
    assert ("monster_builder" in msg.lower()
            or "monster" in msg.lower()), (
        f"RuntimeError message should mention monster_builder. Got: {msg!r}"
    )
    assert stderr_message in msg, (
        f"RuntimeError message should include subprocess stderr "
        f"({stderr_message!r}) for diagnosis. Got: {msg!r}"
    )
