"""
Tests for T5-4 (CH-H2): Consult the NPC compendium before invoking the AI
NPC builder.

Background:
- combat_builder.load_or_create_npc() previously fell straight through to a
  subprocess npc_builder.py invocation whenever the module-local character
  file lookup + fuzzy match both failed. That produced a fresh AI-generated
  NPC whose stats and identity drifted away from canonical compendium
  entries (e.g. "Garrick the Innkeeper" generated anew each module run).
- The central compendium at data/bestiary/npc_compendium.json carries 50+
  canonical NPC identity records. Consulting it first prevents duplicates
  and name drift downstream.

Fix:
- Between the fuzzy-match miss and the npc_builder subprocess call, load
  data/bestiary/npc_compendium.json and look for the requested name. Both
  the snake_case key and the human-readable "name" field are checked using
  a normalized form (lowercase, alphanumerics + underscores only).
- On hit: write the compendium entry to the module-local characters/ dir
  and return WITHOUT invoking subprocess. Add character_type="npc" so the
  rest of the pipeline recognizes it.
- On miss / missing file / malformed file: fall through to the existing
  AI generation path. No exceptions surface.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.generators import combat_builder


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _write_party_tracker(workdir: Path, module: str = "TestModule") -> None:
    (workdir / "party_tracker.json").write_text(json.dumps({
        "module": module,
        "partyMembers": ["hero"],
        "worldConditions": {
            "currentLocationId": "A01",
            "currentAreaId": "A01",
        },
    }))


def _write_compendium(workdir: Path, npcs: dict) -> Path:
    compendium_dir = workdir / "data" / "bestiary"
    compendium_dir.mkdir(parents=True)
    path = compendium_dir / "npc_compendium.json"
    path.write_text(json.dumps({
        "version": "1.0.0",
        "total_npcs": len(npcs),
        "npcs": npcs,
    }))
    return path


def _make_path_manager_stub(workdir: Path):
    """Build a stub ModulePathManager-like object that points every
    character lookup at workdir/characters/<name>.json. The directory is
    created so writes succeed.
    """
    char_dir = workdir / "characters"
    char_dir.mkdir(exist_ok=True)

    class _Stub:
        def get_character_path(self, name):
            return str(char_dir / f"{name}.json")

    return _Stub()


# ---------------------------------------------------------------------------
# Test 1: Compendium hit -> file written from compendium, NO AI call.
# ---------------------------------------------------------------------------

def test_compendium_hit_writes_file_without_invoking_npc_builder(
        tmp_path, monkeypatch):
    """When the requested NPC name maps to a compendium key, the
    module-local character file must be written from the compendium entry
    and the npc_builder subprocess MUST NOT be invoked. Prevents stat
    drift (CH-H2 root cause)."""
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    _write_party_tracker(workdir)
    _write_compendium(workdir, {
        "merchant_gareth": {
            "name": "Merchant Gareth",
            "description": "A portly trader with a vibrant blue tunic.",
            "module": "The_Thornwood_Watch",
        },
    })

    # Path manager hands out workdir-local character paths so the test
    # is fully isolated.
    monkeypatch.setattr(combat_builder, "ModulePathManager",
                        lambda *a, **kw: _make_path_manager_stub(workdir))

    # Force the AI builder subprocess to be observable; if the
    # compendium-first path is missing, the test will see it called.
    subprocess_calls = []

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        subprocess_calls.append(argv)
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)

    result = combat_builder.load_or_create_npc("Merchant Gareth")

    assert subprocess_calls == [], (
        "npc_builder subprocess MUST NOT be invoked when the compendium "
        f"already has the NPC. Got calls: {subprocess_calls!r}"
    )
    assert result is not None, "load_or_create_npc returned None on a compendium hit"
    assert result.get("name") == "Merchant Gareth", (
        f"Expected name='Merchant Gareth', got name={result.get('name')!r}"
    )

    # The character file must actually exist on disk so downstream
    # combat code can read it.
    char_files = list((workdir / "characters").glob("*.json"))
    assert len(char_files) >= 1, (
        f"Expected at least one character file written to "
        f"{workdir / 'characters'}, found none. Compendium-hit path did "
        "not persist the entry."
    )
    written = json.loads(char_files[0].read_text())
    assert written.get("name") == "Merchant Gareth", (
        f"Written file does not carry the compendium name. "
        f"File contents: {written!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: Compendium miss -> fall through to AI generation as before.
# ---------------------------------------------------------------------------

def test_compendium_miss_falls_through_to_npc_builder_subprocess(
        tmp_path, monkeypatch):
    """If the requested NPC name does not appear in the compendium, the
    existing AI generation path must still run. The fix must not block
    legitimate new NPC creation."""
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    _write_party_tracker(workdir)
    # Compendium exists but does NOT have the requested NPC.
    _write_compendium(workdir, {
        "merchant_gareth": {
            "name": "Merchant Gareth",
            "description": "Some unrelated NPC.",
            "module": "The_Thornwood_Watch",
        },
    })

    monkeypatch.setattr(combat_builder, "ModulePathManager",
                        lambda *a, **kw: _make_path_manager_stub(workdir))

    # Make the subprocess "succeed" and write a minimal NPC file so
    # the post-subprocess load step has something to read.
    char_dir = workdir / "characters"

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        # argv looks like [python, npc_builder.py, normalized_name, ...]
        normalized_name = argv[2]
        target = char_dir / f"{normalized_name}.json"
        target.write_text(json.dumps({
            "name": "Brand New Innkeeper",
            "character_type": "npc",
            "level": 1,
        }))
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)

    # Stub _get_party_level to avoid touching real party tracker logic.
    monkeypatch.setattr(combat_builder, "_get_party_level", lambda: 3)

    with patch.object(combat_builder.subprocess, "run",
                      side_effect=_fake_run) as mock_run:
        result = combat_builder.load_or_create_npc("Brand New Innkeeper")
        assert mock_run.called, (
            "npc_builder subprocess MUST be invoked when the compendium "
            "does not contain the requested NPC."
        )

    assert result is not None
    assert result.get("name") == "Brand New Innkeeper"


# ---------------------------------------------------------------------------
# Test 3: Compendium file missing / malformed -> graceful fallback.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario", ["missing", "malformed"])
def test_compendium_missing_or_malformed_falls_back_to_ai(
        tmp_path, monkeypatch, scenario):
    """The compendium lookup must never raise. If the file is missing or
    malformed, the function must fall through to the existing AI path
    so production traffic is not blocked by a corrupt data file."""
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    _write_party_tracker(workdir)

    if scenario == "missing":
        # Do NOT create data/bestiary/npc_compendium.json at all.
        pass
    else:
        compendium_dir = workdir / "data" / "bestiary"
        compendium_dir.mkdir(parents=True)
        # Malformed JSON (truncated)
        (compendium_dir / "npc_compendium.json").write_text(
            '{"npcs": {"merchant_garet'
        )

    monkeypatch.setattr(combat_builder, "ModulePathManager",
                        lambda *a, **kw: _make_path_manager_stub(workdir))

    char_dir = workdir / "characters"

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        normalized_name = argv[2]
        target = char_dir / f"{normalized_name}.json"
        target.write_text(json.dumps({
            "name": "Unknown Vagabond",
            "character_type": "npc",
        }))
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)
    monkeypatch.setattr(combat_builder, "_get_party_level", lambda: 3)

    with patch.object(combat_builder.subprocess, "run",
                      side_effect=_fake_run) as mock_run:
        result = combat_builder.load_or_create_npc("Unknown Vagabond")
        assert mock_run.called, (
            f"In scenario={scenario!r}, the AI builder must still run when "
            "the compendium is unavailable. It was not invoked."
        )

    assert result is not None, (
        f"In scenario={scenario!r}, load_or_create_npc returned None "
        "instead of falling through to AI generation."
    )


# ---------------------------------------------------------------------------
# Test 4: Case-insensitive matching against compendium.
# ---------------------------------------------------------------------------

def test_compendium_match_is_case_and_punctuation_insensitive(
        tmp_path, monkeypatch):
    """Modules may refer to "garrick", "Garrick", or "Garrick the
    Innkeeper" while the compendium key is "garrick_the_innkeeper". The
    lookup must normalize both sides so trivial casing/punctuation
    differences do not produce duplicates."""
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    _write_party_tracker(workdir)
    _write_compendium(workdir, {
        "garrick_the_innkeeper": {
            "name": "Garrick the Innkeeper",
            "description": "A friendly innkeeper.",
            "module": "Some_Module",
        },
    })

    monkeypatch.setattr(combat_builder, "ModulePathManager",
                        lambda *a, **kw: _make_path_manager_stub(workdir))

    subprocess_calls = []

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        subprocess_calls.append(argv)
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)

    # Case + punctuation variant of the canonical name.
    result = combat_builder.load_or_create_npc("garrick the innkeeper")

    assert subprocess_calls == [], (
        "Case/punctuation-variant lookup MUST hit the compendium and "
        f"skip the AI builder. Got subprocess calls: {subprocess_calls!r}"
    )
    assert result is not None
    assert result.get("name") == "Garrick the Innkeeper", (
        "Returned NPC must carry the canonical compendium name "
        f"('Garrick the Innkeeper'), got {result.get('name')!r}."
    )
