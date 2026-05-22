"""
Tests for VAL-H4: cross-reference encounter creatures against bestiary.

`core/validation/validate_module_files.py` validates encounter JSON files
against `encounter_schema.json`, but the schema only enforces presence of
a `monsterType` string -- it does NOT verify that the string resolves to
an actual monster stat block in:

  - data/bestiary/monster_compendium.json (global bestiary)
  - modules/<module>/monsters/*.json     (module-local stat blocks)

An encounter referencing a nonexistent "Ancient Purple Dragon" passes
schema validation today. These tests exercise
`ModuleValidator.validate_encounter_creature_resolution()`, which we are
adding. It must:

  1. Return (True, []) when every enemy creature's monsterType resolves
     to either the global compendium or a module-local monster file.
  2. Return (False, [errors]) listing every unresolved monsterType,
     including the encounter filename and the failing string so a fixer
     can locate the bug.
  3. Skip creatures whose `type` is "player" or "npc" -- only `enemy`
     creatures need to resolve to monster stat blocks.
  4. Return (True, []) (vacuous) when the module has no encounters dir.

Per encounter_schema, the creature `type` enum is
["player", "enemy", "npc"]. Only `enemy` creatures carry a `monsterType`.
The monsterType key format is snake_case (e.g. "giant_spider"), matching
the keys in `monster_compendium.json` and module-local monster filenames.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.validation.validate_module_files import ModuleValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_validator(module_path: Path) -> ModuleValidator:
    """Allocate a ModuleValidator. schema_dir is irrelevant for
    validate_encounter_creature_resolution (only reads bestiary +
    encounter JSON), but the constructor requires it."""
    schema_dir = Path(__file__).resolve().parents[1] / "schemas"
    return ModuleValidator(str(module_path), str(schema_dir))


def _write_global_bestiary(bestiary_path: Path, monster_keys: list) -> None:
    """Write a minimal global monster_compendium.json containing the
    given snake_case keys. Only the key set matters for resolution."""
    data = {
        "version": "1.0.0",
        "monsters": {
            key: {"name": key.replace("_", " ").title()}
            for key in monster_keys
        },
    }
    bestiary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bestiary_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _write_module_local_monster(monsters_dir: Path, key: str) -> None:
    """Write a minimal module-local monster file at
    monsters_dir/<key>.json. Filename (sans .json) is the resolution
    key; matches how module_generator writes module-local monsters."""
    monsters_dir.mkdir(parents=True, exist_ok=True)
    with open(monsters_dir / f"{key}.json", "w", encoding="utf-8") as f:
        json.dump({"name": key.replace("_", " ").title()}, f)


def _write_encounter(path: Path, encounter_id: str, creatures: list,
                     summary: str = "Test encounter") -> None:
    """Write an encounter JSON file with the given creatures list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "encounterId": encounter_id,
        "encounterSummary": summary,
        "creatures": creatures,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Test 1 (positive): encounter referencing known global monsters -> 0 errors
# ---------------------------------------------------------------------------

def test_encounter_creatures_resolve_to_global_bestiary(tmp_path, monkeypatch):
    """When every enemy creature's monsterType matches a key in the
    global monster_compendium.json, the validator must return (True, [])."""
    repo_root = tmp_path / "repo"
    bestiary_path = repo_root / "data" / "bestiary" / "monster_compendium.json"
    _write_global_bestiary(
        bestiary_path,
        monster_keys=["giant_spider", "swarm_of_spiders"],
    )

    module_dir = repo_root / "modules" / "test_module_global"
    _write_encounter(
        module_dir / "encounters" / "encounter_A01-E1.json",
        "A01-E1",
        creatures=[
            {
                "name": "Giant Spider",
                "type": "enemy",
                "monsterType": "giant_spider",
            },
            {
                "name": "Swarm of Spiders",
                "type": "enemy",
                "monsterType": "swarm_of_spiders",
            },
        ],
    )

    monkeypatch.chdir(repo_root)
    validator = _make_validator(module_dir)
    ok, errors = validator.validate_encounter_creature_resolution(module_dir)

    assert ok is True, (
        f"Expected encounter with known monsters to validate cleanly. "
        f"errors={errors}"
    )
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Test 2 (negative): unknown monsterType -> 1 error naming encounter + string
# ---------------------------------------------------------------------------

def test_encounter_with_unknown_monster_fails(tmp_path, monkeypatch):
    """An encounter referencing a creature whose monsterType resolves to
    neither the global compendium nor the module-local monsters dir
    must produce exactly one error, and the error string must mention
    the encounter filename AND the failing monsterType so a fixer can
    find it.

    We intentionally reference ``aboleth`` -- which exists in the REAL
    repo bestiary but is NOT in our fixture bestiary -- so this test
    also doubles as proof that the validator honors the test fixture's
    bestiary (via cwd) and does not silently fall through to the real
    repo bestiary, which would mask the bug under test."""
    repo_root = tmp_path / "repo"
    bestiary_path = repo_root / "data" / "bestiary" / "monster_compendium.json"
    # Bestiary intentionally does NOT contain "aboleth". If the
    # validator were reading the real repo bestiary instead of this
    # fixture, the assertion below would fail (aboleth IS in the real
    # bestiary), proving the validator must honor cwd for isolation.
    _write_global_bestiary(bestiary_path, monster_keys=["giant_spider"])

    module_dir = repo_root / "modules" / "test_module_unknown"
    _write_encounter(
        module_dir / "encounters" / "encounter_B02-E1.json",
        "B02-E1",
        creatures=[
            {
                "name": "Aboleth",
                "type": "enemy",
                "monsterType": "aboleth",
            },
        ],
    )

    monkeypatch.chdir(repo_root)
    validator = _make_validator(module_dir)
    ok, errors = validator.validate_encounter_creature_resolution(module_dir)

    assert ok is False, (
        f"Expected validation to FAIL for unknown monsterType "
        f"'aboleth' (absent from fixture bestiary). Got ok=True with "
        f"errors={errors}."
    )
    assert len(errors) == 1, (
        f"Expected exactly one error for the single unknown monster, "
        f"got: {errors}"
    )
    err = errors[0]
    assert "aboleth" in err, (
        f"Error must include the failing monsterType so a fixer can "
        f"locate the bug. Got: {err!r}"
    )
    assert "encounter_B02-E1.json" in err, (
        f"Error must include the encounter filename so a fixer can "
        f"locate the source. Got: {err!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 (positive): module-local monsters/ resolves -> 0 errors
# ---------------------------------------------------------------------------

def test_encounter_resolves_to_module_local_monsters(tmp_path, monkeypatch):
    """When an enemy's monsterType is not in the global bestiary but
    IS present as a file under modules/<module>/monsters/<key>.json,
    the validator must accept it. Module-local monsters are first-class
    stat blocks created by module_generator and live alongside the
    encounter that references them."""
    repo_root = tmp_path / "repo"
    bestiary_path = repo_root / "data" / "bestiary" / "monster_compendium.json"
    # Empty global bestiary -- resolution must succeed via module-local
    _write_global_bestiary(bestiary_path, monster_keys=[])

    module_dir = repo_root / "modules" / "test_module_local"
    # Module-local stat block lives at modules/<module>/monsters/bandit.json
    _write_module_local_monster(module_dir / "monsters", "bandit")
    _write_encounter(
        module_dir / "encounters" / "encounter_C01-E1.json",
        "C01-E1",
        creatures=[
            {
                "name": "Bandit",
                "type": "enemy",
                "monsterType": "bandit",
            },
        ],
    )

    monkeypatch.chdir(repo_root)
    validator = _make_validator(module_dir)
    ok, errors = validator.validate_encounter_creature_resolution(module_dir)

    assert ok is True, (
        f"Expected module-local monster 'bandit' to resolve via "
        f"modules/<module>/monsters/bandit.json. errors={errors}"
    )
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Test 4 (regression): player-only encounter -> 0 errors
# ---------------------------------------------------------------------------

def test_encounter_with_only_player_creature_passes(tmp_path, monkeypatch):
    """An encounter whose creatures list contains only player (and/or
    npc) entries has no enemies to resolve. The validator must not
    require players to resolve to monster stat blocks -- the type enum
    is ["player", "enemy", "npc"] and only "enemy" carries monsterType.

    Regression guard: previous draft implementations could mistakenly
    look up `creature["name"]` for every entry, which would incorrectly
    flag the player character as an unknown monster."""
    repo_root = tmp_path / "repo"
    bestiary_path = repo_root / "data" / "bestiary" / "monster_compendium.json"
    _write_global_bestiary(bestiary_path, monster_keys=[])

    module_dir = repo_root / "modules" / "test_module_player_only"
    _write_encounter(
        module_dir / "encounters" / "encounter_D01-E1.json",
        "D01-E1",
        creatures=[
            {
                "name": "Norn",
                "type": "player",
            },
        ],
    )

    monkeypatch.chdir(repo_root)
    validator = _make_validator(module_dir)
    ok, errors = validator.validate_encounter_creature_resolution(module_dir)

    assert ok is True, (
        f"Expected player-only encounter to pass with no enemy lookups. "
        f"errors={errors}"
    )
    assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Test 5 (regression): module with no encounters dir -> 0 errors
# ---------------------------------------------------------------------------

def test_module_without_encounters_dir_is_vacuous(tmp_path, monkeypatch):
    """If a module has no encounters/ directory at all, there is
    nothing to validate. The validator must return (True, []) rather
    than crashing on a missing directory."""
    repo_root = tmp_path / "repo"
    bestiary_path = repo_root / "data" / "bestiary" / "monster_compendium.json"
    _write_global_bestiary(bestiary_path, monster_keys=["giant_spider"])

    # Module exists but has no encounters/ subdirectory
    module_dir = repo_root / "modules" / "test_module_no_encounters"
    module_dir.mkdir(parents=True)

    monkeypatch.chdir(repo_root)
    validator = _make_validator(module_dir)
    ok, errors = validator.validate_encounter_creature_resolution(module_dir)

    assert ok is True, (
        f"Expected module with no encounters dir to return "
        f"(True, []). errors={errors}"
    )
    assert errors == [], f"Expected no errors, got: {errors}"
