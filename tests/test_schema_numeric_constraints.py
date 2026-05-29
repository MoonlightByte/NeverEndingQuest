"""
Tests for T4-4 (VAL-H3, VAL-M6, CH-C3 partial): mon_schema.json and
encounter_schema.json must enforce numeric range constraints on key fields
so that nonsensical values (HP=0, negative AC, negative challengeRating)
are rejected at validation time.

Bugs addressed:

  * mon_schema.json defines `hitPoints`, `armorClass`, and `challengeRating`
    as integers/numbers but does NOT set a `minimum`. A generated monster
    with `hitPoints: 0`, `armorClass: -5`, or `challengeRating: 99` would
    validate successfully even though those values break combat math.

  * mon_schema.json defines `maxHitPoints` as a property but the field is
    NOT listed in the top-level `required` array. Combat code reads
    `maxHitPoints` to cap healing; a monster file missing that field
    silently breaks healing logic.

  * encounter_schema.json defines `currentHitPoints` and `maxHitPoints`
    but does NOT set a `minimum`. (It already lists both in `required`.)

This test module covers:
  1. Monster with hitPoints=0 -> fails mon_schema validation
  2. Monster with armorClass=0 -> fails (minimum is 1)
  3. Monster with challengeRating=-1 -> fails (minimum is 0)
  4. Monster missing maxHitPoints -> fails (now required)
  5. Encounter creature with currentHitPoints=0 -> PASSES (dead monster);
     currentHitPoints=-5 -> fails (minimum is 0)
  6. Regression: a valid, fully-populated monster passes mon_schema
  7. Regression: a valid encounter passes encounter_schema
"""

import copy
import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, ValidationError, validate

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
MON_SCHEMA_PATH = SCHEMA_DIR / "mon_schema.json"
ENCOUNTER_SCHEMA_PATH = SCHEMA_DIR / "encounter_schema.json"


# ---------------------------------------------------------------------------
# Schema loading helpers
# ---------------------------------------------------------------------------

def _load_schema(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def mon_schema() -> dict:
    return _load_schema(MON_SCHEMA_PATH)


@pytest.fixture(scope="module")
def encounter_schema() -> dict:
    return _load_schema(ENCOUNTER_SCHEMA_PATH)


# ---------------------------------------------------------------------------
# Valid baseline payload builders. These produce monsters/encounters that
# satisfy every required field with sensible values, so each test can
# clone-and-mutate exactly the field under test.
# ---------------------------------------------------------------------------

def _valid_monster() -> dict:
    return {
        "name": "Test Goblin",
        "size": "Small",
        "type": "humanoid",
        "alignment": "neutral evil",
        "armorClass": 15,
        "hitPoints": 7,
        "maxHitPoints": 7,
        "speed": 30,
        "abilities": {
            "strength": 8,
            "dexterity": 14,
            "constitution": 10,
            "intelligence": 10,
            "wisdom": 8,
            "charisma": 8,
        },
        "savingThrows": [],
        "skills": {"stealth": 6},
        "damageVulnerabilities": [],
        "damageResistances": [],
        "damageImmunities": [],
        "conditionImmunities": [],
        "senses": {"darkvision": 60, "passivePerception": 9},
        "languages": "Common, Goblin",
        "challengeRating": 0.25,
        "specialAbilities": [],
        "actions": [
            {
                "name": "Scimitar",
                "attackBonus": 4,
                "damageDice": "1d6",
                "damageBonus": 2,
                "damageType": "slashing",
            }
        ],
        "legendaryActions": [],
        "condition": "Alive",
    }


def _valid_encounter() -> dict:
    return {
        "encounterId": "E001",
        "encounterSummary": "Two goblins ambush the party on the trail.",
        "creatures": [
            {
                "name": "Eira",
                "type": "player",
                "initiative": 12,
                "status": "alive",
                "conditions": [],
                "actions": {"actionType": "attack", "target": "Goblin 1"},
                "currentHitPoints": 24,
                "maxHitPoints": 24,
            },
            {
                "name": "Goblin 1",
                "type": "enemy",
                "monsterType": "goblin",
                "initiative": 9,
                "status": "alive",
                "conditions": [],
                "actions": {"actionType": "attack", "target": "Eira"},
                "currentHitPoints": 7,
                "maxHitPoints": 7,
            },
        ],
    }


# ---------------------------------------------------------------------------
# Test 1: hitPoints=0 must fail mon_schema validation.
# ---------------------------------------------------------------------------

def test_monster_with_hitpoints_zero_fails(mon_schema):
    monster = _valid_monster()
    monster["hitPoints"] = 0

    with pytest.raises(ValidationError) as exc:
        validate(instance=monster, schema=mon_schema)

    msg = str(exc.value).lower()
    assert "hitpoints" in msg or "minimum" in msg or "0" in msg, (
        f"Expected validation error to mention hitPoints/minimum/0; got: {exc.value}"
    )


# ---------------------------------------------------------------------------
# Test 2: armorClass=0 must fail (minimum is 1).
# ---------------------------------------------------------------------------

def test_monster_with_armorclass_zero_fails(mon_schema):
    monster = _valid_monster()
    monster["armorClass"] = 0

    with pytest.raises(ValidationError) as exc:
        validate(instance=monster, schema=mon_schema)

    msg = str(exc.value).lower()
    assert "armorclass" in msg or "minimum" in msg, (
        f"Expected validation error to mention armorClass/minimum; got: {exc.value}"
    )


# ---------------------------------------------------------------------------
# Test 3: challengeRating=-1 must fail (minimum is 0).
# ---------------------------------------------------------------------------

def test_monster_with_negative_challenge_rating_fails(mon_schema):
    monster = _valid_monster()
    monster["challengeRating"] = -1

    with pytest.raises(ValidationError) as exc:
        validate(instance=monster, schema=mon_schema)

    msg = str(exc.value).lower()
    assert "challengerating" in msg or "minimum" in msg, (
        f"Expected validation error to mention challengeRating/minimum; got: {exc.value}"
    )


# ---------------------------------------------------------------------------
# Test 4: missing maxHitPoints must fail (newly required).
# ---------------------------------------------------------------------------

def test_monster_missing_max_hitpoints_fails(mon_schema):
    monster = _valid_monster()
    del monster["maxHitPoints"]

    with pytest.raises(ValidationError) as exc:
        validate(instance=monster, schema=mon_schema)

    msg = str(exc.value).lower()
    assert "maxhitpoints" in msg or "required" in msg, (
        f"Expected validation error to mention maxHitPoints/required; got: {exc.value}"
    )


# ---------------------------------------------------------------------------
# Test 5: encounter creature with currentHitPoints=0 must PASS.
# VAL-H3 regression guard: a monster reduced to 0 HP is dead -- a legitimate,
# common combat state. update_encounter.py validates the full encounter on
# every update, so a minimum of 1 would reject every kill update and silently
# drop the monster's death. currentHitPoints minimum must be 0; a NEGATIVE
# value must still fail.
# ---------------------------------------------------------------------------

def test_encounter_with_zero_current_hitpoints_passes(encounter_schema):
    encounter = _valid_encounter()
    encounter["creatures"][1]["currentHitPoints"] = 0

    # Must NOT raise: 0 HP is a dead-but-valid creature.
    validate(instance=encounter, schema=encounter_schema)


def test_encounter_with_negative_current_hitpoints_fails(encounter_schema):
    encounter = _valid_encounter()
    encounter["creatures"][1]["currentHitPoints"] = -5

    with pytest.raises(ValidationError) as exc:
        validate(instance=encounter, schema=encounter_schema)

    msg = str(exc.value).lower()
    assert "currenthitpoints" in msg or "minimum" in msg or "-5" in msg, (
        f"Expected validation error to mention currentHitPoints/minimum; got: {exc.value}"
    )


# ---------------------------------------------------------------------------
# Test 6 (regression): a fully valid monster passes mon_schema.
# ---------------------------------------------------------------------------

def test_valid_monster_passes_schema(mon_schema):
    monster = _valid_monster()

    # Should not raise.
    validate(instance=monster, schema=mon_schema)

    # Sanity: confirm there are zero errors via the iterator API too.
    validator = Draft7Validator(mon_schema)
    errors = sorted(validator.iter_errors(monster), key=lambda e: e.path)
    assert errors == [], (
        f"Expected zero validation errors for a known-good monster, got: "
        f"{[e.message for e in errors]}"
    )


# ---------------------------------------------------------------------------
# Test 7 (regression): a fully valid encounter passes encounter_schema.
# ---------------------------------------------------------------------------

def test_valid_encounter_passes_schema(encounter_schema):
    encounter = _valid_encounter()

    # Should not raise.
    validate(instance=encounter, schema=encounter_schema)

    validator = Draft7Validator(encounter_schema)
    errors = sorted(validator.iter_errors(encounter), key=lambda e: e.path)
    assert errors == [], (
        f"Expected zero validation errors for a known-good encounter, got: "
        f"{[e.message for e in errors]}"
    )
