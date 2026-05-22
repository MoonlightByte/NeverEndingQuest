"""
Tests for VAL-L1: module_debugger.load_schemas() must not attempt to
load `npc_schema.json` because no such file exists in `schemas/`.

`module_debugger.py:86` listed `"npc_schema.json"` in the schemas to
load. The file was never created, so every debugger run logged a
warning ("Schema not found: npc_schema.json"). The lookup result was
never read by validate_schema_compliance() or any other code path --
nothing in module_debugger.py reads self.schemas["npc_schema.json"]
or self.schemas["npc"]. The entry was pure dead code.

Decision per T4-8: REMOVE the dead lookup. Creating a real npc_schema
would be a deliberate larger task and is out of scope here.

These tests cover:
  1. load_schemas() does not emit any warning mentioning npc_schema
     (the dead lookup is gone).
  2. Regression: other valid schemas (module_schema.json,
     char_schema.json, etc.) are still loaded successfully so we
     didn't accidentally remove anything real.
"""

import os
import sys
from io import StringIO
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from module_debugger import ModuleDebugger


@pytest.fixture
def schemas_cwd(monkeypatch):
    """ModuleDebugger.load_schemas() opens schema files by bare filename
    relative to the current working directory, so the schemas/ dir must
    be cwd for the loader to find anything. This mirrors how the real
    pipeline invokes it from validate_module_files / module_generator.
    """
    schemas_dir = REPO_ROOT / "schemas"
    assert schemas_dir.is_dir(), (
        f"schemas/ dir missing at {schemas_dir}; test environment is wrong."
    )
    monkeypatch.chdir(schemas_dir)
    return schemas_dir


# ---------------------------------------------------------------------------
# Test 1: No npc_schema warning is emitted on load_schemas()
# ---------------------------------------------------------------------------

def test_load_schemas_emits_no_npc_schema_warning(schemas_cwd, capsys):
    """After T4-8, load_schemas() must not list npc_schema.json as a
    schema to load, so no 'Schema not found: npc_schema.json' warning
    should ever be printed and no such warning should be recorded in
    self.warnings.
    """
    dbg = ModuleDebugger()
    ok = dbg.load_schemas()
    assert ok is True, "load_schemas() returned False unexpectedly"

    # stdout/stderr should not mention npc_schema at all.
    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert "npc_schema" not in combined_output, (
        "load_schemas() printed a warning mentioning npc_schema; the "
        "dead lookup is still present. Captured output:\n"
        f"{combined_output}"
    )

    # The structured warnings list must also be free of npc_schema
    # references (log_warning appends a 'WARNING: ...' string).
    npc_warnings = [w for w in dbg.warnings if "npc_schema" in w]
    assert npc_warnings == [], (
        f"self.warnings contains npc_schema entries: {npc_warnings}"
    )

    # And no key resembling npc_schema should be loaded either.
    npc_keys = [k for k in dbg.schemas.keys() if "npc" in k.lower()]
    assert npc_keys == [], (
        f"self.schemas should not have any 'npc'-keyed entry, got: {npc_keys}"
    )


# ---------------------------------------------------------------------------
# Test 2: Regression -- valid schemas still load
# ---------------------------------------------------------------------------

def test_load_schemas_still_loads_other_schemas(schemas_cwd):
    """Removing the dead npc_schema.json entry must not affect any of
    the real schema lookups. This guards against an accidental
    deletion of a sibling entry (e.g. removing more than one line).
    """
    dbg = ModuleDebugger()
    assert dbg.load_schemas() is True

    # These schema files exist on disk in schemas/ and must still load.
    required_loaded = [
        "module_schema.json",
        "loca_schema.json",
        "plot_schema.json",
        "party_schema.json",
        "char_schema.json",
        "mon_schema.json",
        "map_schema.json",
        "encounter_schema.json",
        "room_schema.json",
    ]
    missing = [s for s in required_loaded if s not in dbg.schemas]
    assert missing == [], (
        f"Expected schemas still missing after T4-8 fix: {missing}. "
        f"Loaded keys: {sorted(dbg.schemas.keys())}"
    )
