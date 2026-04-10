import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.validation.validate_module_files import ModuleValidator
from core.ai import conversation_utils
from updates.update_character_info import repair_character_data
from utils.character_sheet_contract import (
    extract_json_object,
    repair_required_ammunition_field,
    repair_runtime_character_sheet,
    repair_startup_character_sheet,
)


SAMPLE_CHARACTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "modules"
    / "backups"
    / "restore_backup_20250907_085917"
    / "characters"
    / "test_currency_character.json"
)


def _load_sample_character():
    with open(SAMPLE_CHARACTER_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_extract_json_object_handles_prose_and_fences():
    content = "Here is the result:\n```json\n{\"name\": \"Lux\", \"ammunition\": []}\n```\nThanks!"

    extracted = extract_json_object(content)

    assert extracted is not None
    assert json.loads(extracted) == {"name": "Lux", "ammunition": []}


def test_startup_repair_adds_ammunition_and_currency_defaults():
    character = _load_sample_character()
    character.pop("ammunition", None)
    character.pop("temporaryEffects", None)
    character.pop("injuries", None)
    character.pop("equipment_effects", None)
    character.pop("feats", None)
    character["currency"] = {"silver": 4, "copper": 2}

    repaired, changes = repair_startup_character_sheet(character)

    assert repaired["ammunition"] == []
    assert repaired["temporaryEffects"] == []
    assert repaired["injuries"] == []
    assert repaired["equipment_effects"] == []
    assert repaired["feats"] == []
    assert repaired["currency"] == {"gold": 10, "silver": 4, "copper": 2}
    assert "ammunition=default_list" in changes


def test_required_ammunition_repair_backfills_list_only():
    repaired, changes = repair_required_ammunition_field({"name": "Lux", "ammunition": None})

    assert repaired["ammunition"] == []
    assert "ammunition=default_list" in changes


def test_update_character_repair_adds_missing_ammunition():
    repaired = repair_character_data({"equipment": []})

    assert repaired["ammunition"] == []


def test_runtime_repair_backfills_runtime_safe_fields():
    repaired, changes = repair_runtime_character_sheet({"name": "Broken Sheet"}, character_type="player")

    assert repaired["character_type"] == "player"
    assert repaired["ammunition"] == []
    assert repaired["equipment"] == []
    assert repaired["abilities"]["strength"] == 10
    assert repaired["currency"] == {"gold": 0, "silver": 0, "copper": 0}
    assert changes


def test_runtime_repair_normalizes_list_item_shapes():
    repaired, _ = repair_runtime_character_sheet(
        {
            "name": "Broken Sheet",
            "equipment": ["rope"],
            "ammunition": [{"quantity": "3"}],
            "classFeatures": [{"description": "Feature text"}],
            "racialTraits": [{"name": None, "description": None}],
            "temporaryEffects": ["blessed"],
            "feats": ["Alert"],
            "attacksAndSpellcasting": [{"name": None, "damageDice": None}],
        },
        character_type="player",
    )

    assert repaired["equipment"][0]["item_name"] == "rope"
    assert repaired["equipment"][0]["quantity"] == 1
    assert repaired["ammunition"][0]["name"] == "Unknown Ammunition"
    assert repaired["ammunition"][0]["quantity"] == 1
    assert repaired["classFeatures"][0]["name"] == "Unknown Feature"
    assert repaired["racialTraits"][0]["name"] == "Unknown Trait"
    assert repaired["temporaryEffects"][0]["name"] == "blessed"
    assert repaired["feats"][0]["name"] == "Alert"
    assert repaired["attacksAndSpellcasting"][0]["name"] == "Unknown Attack"


def test_module_validator_repairs_legacy_character_ammunition():
    character = _load_sample_character()
    character.pop("ammunition", None)

    with TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)
        characters_dir = module_dir / "characters"
        characters_dir.mkdir(parents=True, exist_ok=True)
        test_file = characters_dir / "legacy_character.json"
        test_file.write_text(json.dumps(character, indent=2), encoding="utf-8")

        validator = ModuleValidator(str(module_dir), str(Path(__file__).resolve().parents[1] / "schemas"))
        validator.load_schemas()
        success, error = validator.validate_file(test_file, "character")

        assert success is True
        assert error is None


def test_update_character_data_handles_missing_ammunition(monkeypatch, tmp_path):
    character_file = tmp_path / "smashing_jack.json"
    sample = _load_sample_character()
    sample.pop("ammunition", None)
    character_file.write_text(json.dumps(sample), encoding="utf-8")

    class DummyPathManager:
        def __init__(self, _module):
            pass

        def get_character_path(self, _name):
            return str(character_file)

    monkeypatch.setattr(conversation_utils, "ModulePathManager", DummyPathManager)
    monkeypatch.setattr(
        "updates.update_character_info.normalize_character_name",
        lambda value: value,
    )

    history = conversation_utils.update_character_data(
        conversation_history=[],
        party_tracker_data={"module": "The_Thornwood_Watch", "partyMembers": ["smashing_jack"], "partyNPCs": []},
    )

    character_msgs = [m for m in history if m["role"] == "system" and "Here's the updated character data for" in m["content"]]
    assert character_msgs
    assert "\nAMMO:" in character_msgs[0]["content"]
