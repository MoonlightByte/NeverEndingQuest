"""Tests for T3-2 (CH-M1): character builders use atomic safe_write_json.

The legacy save_json(file_name, data) functions in:
  - core/generators/npc_builder.py        (line 89-97)
  - core/generators/monster_builder.py    (line 92-106)
  - core/generators/combat_builder.py     (line 71-78)

wrote JSON with a non-atomic open()+json.dump() pattern. A process crash
mid-write would produce corrupt JSON, and downstream regeneration on a
corrupt file produces inconsistent module state.

T3-2 replaces each save_json body with a call to
utils.file_operations.safe_write_json(filepath, data). The function
signature -- save_json(file_name, data) -- is preserved so callers do
not need to change.

These tests verify, per module, that:
  1. safe_write_json is imported into the module namespace so it can be
     patched (i.e., `from utils.file_operations import safe_write_json`).
  2. save_json forwards its arguments to safe_write_json in (filepath,
     data) order -- NOT reversed.
  3. The save_json source no longer contains the non-atomic
     `open(...'w')` + `json.dump(...)` pattern. A source-level scan of
     the function body is the only reliable way to catch a partial
     migration where the helper is imported but not used.

Tests use mock.patch on the in-module safe_write_json reference to
capture exact argument order without writing real files.
"""

import inspect
import os
import re
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import npc_builder as npc_mod
from core.generators import monster_builder as mon_mod
from core.generators import combat_builder as combat_mod


# ---------------------------------------------------------------------------
# Helper: source-level scan for the non-atomic write pattern
# ---------------------------------------------------------------------------

_OPEN_WRITE_RE = re.compile(r"open\s*\(\s*[^,)]+,\s*['\"]w['\"]")


def _save_json_source(module) -> str:
    """Return the source of the module's save_json function."""
    return inspect.getsource(module.save_json)


def _assert_no_direct_open_write(module, name: str):
    """Source-level check: save_json must not call open(..., 'w') directly."""
    src = _save_json_source(module)
    matches = _OPEN_WRITE_RE.findall(src)
    assert not matches, (
        f"{name}.save_json still contains a direct open(..., 'w') call -- "
        f"T3-2 requires routing through safe_write_json for atomic writes.\n"
        f"Source:\n{src}"
    )
    assert "json.dump" not in src, (
        f"{name}.save_json still calls json.dump -- T3-2 requires routing "
        f"through safe_write_json (which handles dump internally) for "
        f"atomic writes.\nSource:\n{src}"
    )


# ---------------------------------------------------------------------------
# npc_builder
# ---------------------------------------------------------------------------

def test_npc_builder_imports_safe_write_json():
    """safe_write_json must be importable from npc_builder namespace so
    mock.patch on npc_mod.safe_write_json works at the callsite."""
    assert hasattr(npc_mod, "safe_write_json"), (
        "npc_builder.py must `from utils.file_operations import "
        "safe_write_json` for the atomic save_json migration."
    )


def test_npc_builder_save_json_uses_safe_write_json(tmp_path):
    """save_json(file_name, data) must forward to safe_write_json(filepath,
    data) -- NOT reversed (data, filepath)."""
    target = str(tmp_path / "npc.json")
    payload = {"name": "Test NPC", "race": "Human", "class": "Fighter"}

    with mock.patch.object(npc_mod, "safe_write_json", return_value=True) as m:
        result = npc_mod.save_json(target, payload)

    assert m.call_count == 1, "save_json must delegate to safe_write_json exactly once"
    args, _kwargs = m.call_args
    # First positional arg must be the filepath, NOT the dict.
    assert args[0] == target, (
        f"safe_write_json got filepath={args[0]!r}, expected {target!r} "
        f"-- arguments may be reversed."
    )
    # Second positional arg must be the data dict, NOT the filename string.
    assert args[1] is payload, (
        f"safe_write_json got data={args[1]!r}, expected the payload dict "
        f"-- arguments may be reversed."
    )
    assert isinstance(args[0], str)
    assert isinstance(args[1], dict)
    # Return value must propagate so callers can detect failure.
    assert result is True


def test_npc_builder_save_json_propagates_failure(tmp_path):
    """save_json must return False when safe_write_json returns False."""
    with mock.patch.object(npc_mod, "safe_write_json", return_value=False):
        result = npc_mod.save_json(str(tmp_path / "x.json"), {"a": 1})
    assert result is False


def test_npc_builder_save_json_no_direct_open_write():
    """Source-level scan: save_json must not contain open(..., 'w') or
    json.dump -- those bypass the atomic write."""
    _assert_no_direct_open_write(npc_mod, "npc_builder")


# ---------------------------------------------------------------------------
# monster_builder
# ---------------------------------------------------------------------------

def test_monster_builder_imports_safe_write_json():
    """safe_write_json must be importable from monster_builder namespace."""
    assert hasattr(mon_mod, "safe_write_json"), (
        "monster_builder.py must `from utils.file_operations import "
        "safe_write_json` for the atomic save_json migration."
    )


def test_monster_builder_save_json_uses_safe_write_json(tmp_path):
    """save_json(file_name, data) must forward to safe_write_json(filepath,
    data) -- NOT reversed."""
    target = str(tmp_path / "monster.json")
    payload = {"name": "Goblin", "type": "humanoid", "hitPoints": 7}

    with mock.patch.object(mon_mod, "safe_write_json", return_value=True) as m:
        result = mon_mod.save_json(target, payload)

    assert m.call_count == 1
    args, _kwargs = m.call_args
    assert args[0] == target, (
        f"safe_write_json got filepath={args[0]!r}, expected {target!r}"
    )
    assert args[1] is payload, (
        f"safe_write_json got data={args[1]!r}, expected the payload dict"
    )
    assert isinstance(args[0], str)
    assert isinstance(args[1], dict)
    assert result is True


def test_monster_builder_save_json_propagates_failure(tmp_path):
    """save_json must return False when safe_write_json returns False."""
    with mock.patch.object(mon_mod, "safe_write_json", return_value=False):
        result = mon_mod.save_json(str(tmp_path / "x.json"), {"a": 1})
    assert result is False


def test_monster_builder_save_json_no_direct_open_write():
    """Source-level scan: save_json must not contain open(..., 'w') or
    json.dump."""
    _assert_no_direct_open_write(mon_mod, "monster_builder")


# ---------------------------------------------------------------------------
# combat_builder
# ---------------------------------------------------------------------------

def test_combat_builder_imports_safe_write_json():
    """safe_write_json must be importable from combat_builder namespace."""
    assert hasattr(combat_mod, "safe_write_json"), (
        "combat_builder.py must `from utils.file_operations import "
        "safe_write_json` for the atomic save_json migration."
    )


def test_combat_builder_save_json_uses_safe_write_json(tmp_path):
    """save_json(file_name, data) must forward to safe_write_json(filepath,
    data) -- NOT reversed. combat_builder.save_json saves encounter and
    party_tracker data; lists are also valid payloads."""
    target = str(tmp_path / "encounter.json")
    payload = {"encounterId": "NC01-E1", "monsters": []}

    with mock.patch.object(combat_mod, "safe_write_json", return_value=True) as m:
        result = combat_mod.save_json(target, payload)

    assert m.call_count == 1
    args, _kwargs = m.call_args
    assert args[0] == target, (
        f"safe_write_json got filepath={args[0]!r}, expected {target!r}"
    )
    assert args[1] is payload, (
        f"safe_write_json got data={args[1]!r}, expected the payload dict"
    )
    assert isinstance(args[0], str)
    assert isinstance(args[1], dict)
    assert result is True


def test_combat_builder_save_json_propagates_failure(tmp_path):
    """save_json must return False when safe_write_json returns False."""
    with mock.patch.object(combat_mod, "safe_write_json", return_value=False):
        result = combat_mod.save_json(str(tmp_path / "x.json"), {"a": 1})
    assert result is False


def test_combat_builder_save_json_no_direct_open_write():
    """Source-level scan: save_json must not contain open(..., 'w') or
    json.dump."""
    _assert_no_direct_open_write(combat_mod, "combat_builder")
