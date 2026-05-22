"""
Tests for T5-4 (CH-H2): Consult the NPC compendium before invoking the AI
NPC builder so canonical identities are preserved without losing the
AI-generated stat block.

Background:
- combat_builder.load_or_create_npc() previously fell straight through to a
  subprocess npc_builder.py invocation whenever the module-local character
  file lookup + fuzzy match both failed. That produced a fresh AI-generated
  NPC whose name drifted away from canonical compendium entries
  (e.g. "Garrick the Innkeeper" vs "Garrick Innkeeper" vs "Garrick").
- The central compendium at data/bestiary/npc_compendium.json carries 50+
  canonical NPC identity records (name + description + module). The
  compendium is identity-only -- it does NOT carry stat blocks
  (HP, AC, abilities, actions). Combatants need stats.

Fix (option a from review):
- Between the fuzzy-match miss and the npc_builder subprocess call, load
  data/bestiary/npc_compendium.json and look for the requested name. Both
  the snake_case key and the human-readable "name" field are checked using
  a normalized form (lowercase, alphanumerics + underscores only).
- On hit: PIN the canonical name from the compendium entry, then still
  invoke npc_builder.py with that canonical name so it generates an
  appropriate stat block. The resulting file is keyed off the canonical
  name, so subsequent surface-form references resolve via local file.
- On miss / missing file / malformed file: fall through to the existing
  AI generation path with the originally-requested name. No exceptions
  surface.
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
# Test 1: Compendium hit -> subprocess called with canonical name, stats
# generated, file written under canonical name.
# ---------------------------------------------------------------------------

def test_compendium_hit_invokes_npc_builder_with_canonical_name(
        tmp_path, monkeypatch):
    """On compendium hit, the AI npc_builder MUST still be invoked so a
    valid stat block is generated -- but with the CANONICAL name pinned
    from the compendium (not the originally-requested possibly-mistyped
    surface form). This preserves identity without producing a stat-less
    combatant."""
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

    char_dir = workdir / "characters"
    subprocess_calls = []

    # Subprocess simulates a successful npc_builder run that writes a
    # full stat block keyed off whatever name argv[2] supplies.
    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        subprocess_calls.append(argv)
        normalized_name = argv[2]
        target = char_dir / f"{normalized_name}.json"
        target.write_text(json.dumps({
            "name": "Merchant Gareth",
            "characterType": "npc",
            "hitPoints": 27,
            "armorClass": 12,
            "level": 3,
        }))
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)
    monkeypatch.setattr(combat_builder, "_get_party_level", lambda: 3)

    # Call with the canonical surface form -- compendium should still
    # pin it (identity normalization happens via _normalize_compendium_key).
    result = combat_builder.load_or_create_npc("Merchant Gareth")

    # Subprocess MUST be called so a real stat block exists.
    assert len(subprocess_calls) == 1, (
        "On a compendium hit, npc_builder subprocess MUST be invoked "
        "(option a) so a stat block is generated. Got "
        f"{len(subprocess_calls)} calls: {subprocess_calls!r}"
    )
    # And it MUST be invoked with the canonical name (normalized form
    # of 'Merchant Gareth' -> 'merchant_gareth'), not some other variant.
    invoked_name = subprocess_calls[0][2]
    assert invoked_name == "merchant_gareth", (
        "npc_builder must receive the CANONICAL normalized name "
        f"('merchant_gareth'). Got {invoked_name!r}."
    )

    assert result is not None, "load_or_create_npc returned None on a compendium hit"
    assert result.get("name") == "Merchant Gareth", (
        f"Expected name='Merchant Gareth', got name={result.get('name')!r}"
    )
    # Stat block must be present (this is the bug the fix prevents).
    assert result.get("hitPoints") == 27, (
        "Result is missing a real stat block. The compendium-only write "
        "regression would surface as hitPoints unset or defaulted."
    )
    assert result.get("characterType") == "npc", (
        "Result must carry characterType (camelCase) so existing "
        "fuzzy-match code recognizes it as an NPC. Got "
        f"{result.get('characterType')!r}."
    )


def test_compendium_hit_pins_canonical_name_for_variant_input(
        tmp_path, monkeypatch):
    """If the module references the NPC under a SHORT surface form
    that matches the compendium KEY (which may differ from the longer
    canonical 'name' field), the subprocess MUST receive the
    CANONICAL name (normalized form of compendium 'name' field), not
    the originally-requested short form. This guarantees that future
    references to the longer form also resolve to the same file."""
    workdir = tmp_path
    monkeypatch.chdir(workdir)

    _write_party_tracker(workdir)
    # Realistic compendium shape: key is a short identifier, "name"
    # carries the full canonical title.
    _write_compendium(workdir, {
        "garrick": {
            "name": "Garrick the Innkeeper",
            "description": "A friendly innkeeper.",
            "module": "Some_Module",
        },
    })

    monkeypatch.setattr(combat_builder, "ModulePathManager",
                        lambda *a, **kw: _make_path_manager_stub(workdir))

    char_dir = workdir / "characters"
    subprocess_calls = []

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        subprocess_calls.append(argv)
        normalized_name = argv[2]
        (char_dir / f"{normalized_name}.json").write_text(json.dumps({
            "name": "Garrick the Innkeeper",
            "characterType": "npc",
            "hitPoints": 18,
        }))
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)
    monkeypatch.setattr(combat_builder, "_get_party_level", lambda: 2)

    # Module references the NPC by the short key. Without canonical
    # pinning, npc_builder would be invoked with "garrick" and produce
    # a file at characters/garrick.json -- so a later reference to
    # "Garrick the Innkeeper" would miss the local file and re-trigger
    # AI generation, defeating name-drift prevention.
    result = combat_builder.load_or_create_npc("Garrick")

    assert len(subprocess_calls) == 1, (
        f"Expected exactly one subprocess invocation, got "
        f"{subprocess_calls!r}"
    )
    invoked_name = subprocess_calls[0][2]
    # 'Garrick the Innkeeper' normalized via format_type_name ->
    # 'garrick_the_innkeeper'. If canonical pinning is missing, the
    # subprocess would receive 'garrick' instead.
    assert invoked_name == "garrick_the_innkeeper", (
        "npc_builder must receive the CANONICAL normalized name "
        f"('garrick_the_innkeeper'), NOT the originally-requested "
        f"surface form ('garrick'). Got {invoked_name!r}."
    )
    # File must land at the canonical location, not the short-form
    # location.
    assert (char_dir / "garrick_the_innkeeper.json").exists(), (
        "Expected the canonical file to be written. Files in dir: "
        f"{list(char_dir.glob('*.json'))!r}"
    )
    assert not (char_dir / "garrick.json").exists(), (
        "Short-form file must NOT be written -- canonical pinning "
        "would not be effective if it were."
    )
    assert result is not None
    assert result.get("name") == "Garrick the Innkeeper"


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
            "characterType": "npc",
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
            "characterType": "npc",
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
# Test 4: Case-insensitive matching against compendium, with canonical
# name pinning.
# ---------------------------------------------------------------------------

def test_compendium_match_is_case_and_punctuation_insensitive(
        tmp_path, monkeypatch):
    """Modules may refer to "garrick the innkeeper", "Garrick The
    Innkeeper", or "garrick_the_innkeeper" while the canonical name is
    "Garrick the Innkeeper". The lookup must normalize both sides so
    trivial casing/punctuation differences resolve to the same
    canonical NPC and feed the same canonical name into npc_builder."""
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

    char_dir = workdir / "characters"
    subprocess_calls = []

    def _fake_run(argv, capture_output=False, text=False, **kwargs):
        subprocess_calls.append(argv)
        normalized_name = argv[2]
        (char_dir / f"{normalized_name}.json").write_text(json.dumps({
            "name": "Garrick the Innkeeper",
            "characterType": "npc",
            "hitPoints": 22,
        }))
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout="", stderr="",
        )

    monkeypatch.setattr(combat_builder.subprocess, "run", _fake_run)
    monkeypatch.setattr(combat_builder, "_get_party_level", lambda: 3)

    # Case + punctuation variant of the canonical name.
    result = combat_builder.load_or_create_npc("garrick the innkeeper")

    # Subprocess IS called -- but always with the canonical normalized
    # name so identity is preserved across all surface variants.
    assert len(subprocess_calls) == 1, (
        f"Expected exactly one subprocess invocation, got "
        f"{subprocess_calls!r}"
    )
    invoked_name = subprocess_calls[0][2]
    assert invoked_name == "garrick_the_innkeeper", (
        "Case/punctuation-variant lookup MUST resolve to the canonical "
        "normalized name in the subprocess argv "
        f"('garrick_the_innkeeper'), got {invoked_name!r}."
    )
    assert result is not None
    assert result.get("name") == "Garrick the Innkeeper", (
        "Returned NPC must carry the canonical compendium name "
        f"('Garrick the Innkeeper'), got {result.get('name')!r}."
    )
    assert result.get("hitPoints") == 22, (
        "Returned NPC must carry the AI-generated stat block, got "
        f"hitPoints={result.get('hitPoints')!r}."
    )
