"""D-1323-1: offline casting payment and archived origin grants.

Provider calls are scripted; networking and operator credentials are forbidden
by the existing wizard fixture. Resource subtraction uses the real NQL binary.
"""
import copy
import importlib
import json
from types import SimpleNamespace

import pytest

from test_startup_review_provenance import ROOT, wizard  # noqa: F401


NAME = "Magic Initiate (Wizard)"
BINDING = [{"spell": "longstrider", "resource": NAME}]


@pytest.fixture(autouse=True)
def offline(wizard, monkeypatch):
    from core.nql import creation_scope

    # Load the repository's actual choice tables, without using a live save.
    original = creation_scope._Data
    previous = __import__("os").getcwd()
    monkeypatch.chdir(ROOT)
    data = original()
    monkeypatch.chdir(previous)
    monkeypatch.setattr(creation_scope, "_Data", lambda: copy.deepcopy(data))
    return data


@pytest.mark.parametrize("choice,expected", [
    ({"kind": "feature", "featureName": NAME}, {"featureUseDelta": {NAME: -1}}),
    ({"kind": "slot", "level": 1}, {"spellSlotDelta": {"level1": -1}}),
    ({"kind": "slot", "level": 9}, {"spellSlotDelta": {"level9": -1}}),
])
def test_casting_payment(choice, expected):
    from core.nql.resources import casting_resource_delta
    assert casting_resource_delta(choice) == expected


@pytest.mark.parametrize("choice,message", [
    (None, "must be an object"), ([], "must be an object"),
    ({}, "kind must be"), ({"kind": "other"}, "kind must be"),
    ({"kind": "feature"}, "requires featureName"),
    ({"kind": "feature", "featureName": ""}, "requires featureName"),
    ({"kind": "feature", "featureName": " "}, "requires featureName"),
    ({"kind": "feature", "featureName": 1}, "requires featureName"),
    *[({"kind": "slot", "level": level}, "integer level 1..9")
      for level in (None, 0, 10, -1, True, 1.0, "1")],
])
def test_casting_payment_refusals(choice, message):
    from core.nql.resources import casting_resource_delta
    with pytest.raises(ValueError, match=message):
        casting_resource_delta(choice)


def _archive(folder, data, sheet_path, background_key="sage"):
    from core.nql.creation_scope import _feat_spell_points
    background = data.backgrounds()[background_key]
    sid = next(sid for sid, point in _feat_spell_points(background, data)
               if point.get("kind") != "cantrip"
               and str(point.get("option_source", "")).startswith("spells:"))
    records = [
        ("assistant", {"decision": "finalize_character", "intent": {
            "species_key": "elf", "background_key": background_key,
            "choices": {sid: ["longstrider"]}}}),
        ("system", {"task_purpose": "startup_engine_build", "startup_id": "test"}),
        ("system", {"startup_checkpoint_version": 1, "startup_id": "test",
                    "character_path": str(sheet_path)}),
    ]
    (folder / "startup_conversation_archive_001.json").write_text(
        json.dumps([{"role": role, "content": json.dumps(record)}
                    for role, record in records]), encoding="utf-8")


def test_recovery_from_paired_archive(tmp_path, offline):
    from core.leveling.creation_picks import recover_feat_spell_bindings
    path = tmp_path / "hero.json"
    _archive(tmp_path, offline, path)
    sheet = {"feats": [{"name": NAME}, {"name": "Alert"}]}
    assert recover_feat_spell_bindings(sheet, str(path), str(tmp_path))
    assert sheet["feats"] == [{"name": NAME, "grantedSpells": BINDING}, {"name": "Alert"}]


def test_recovery_without_archive_unchanged(tmp_path):
    from core.leveling.creation_picks import recover_feat_spell_bindings
    sheet = {"feats": [{"name": NAME}]}
    before = copy.deepcopy(sheet)
    assert not recover_feat_spell_bindings(sheet, str(tmp_path / "hero.json"), str(tmp_path))
    assert sheet == before


@pytest.mark.parametrize("feats", [
    [{"name": NAME, "grantedSpells": BINDING}, {"name": "Alert"}],
    [{"name": "Alert"}], [{"name": "Tough"}], [],
])
def test_bound_or_non_spell_feats_never_read_archive(feats, monkeypatch):
    from core.leveling import creation_picks
    def forbidden(*args):
        pytest.fail("Archive must not be read for this sheet")
    monkeypatch.setattr(creation_picks, "creation_picks", forbidden)
    sheet = {"feats": copy.deepcopy(feats)}
    assert not creation_picks.recover_feat_spell_bindings(sheet, "hero.json")
    assert sheet["feats"] == feats


def test_recovery_uses_origin_name_fallback(tmp_path, offline, monkeypatch):
    from core.nql import creation_scope
    from core.leveling.creation_picks import recover_feat_spell_bindings
    data = copy.deepcopy(offline)
    background = data.backgrounds()["sage"]
    background.pop("feat", None)
    origin = next(f for f in data.origins["origin_feats"]
                  if f["key"] == background["feat_ref"]["feat_key"])
    sheet = {"feats": [{"name": origin["name"]}]}
    path = tmp_path / "hero.json"
    _archive(tmp_path, data, path)
    monkeypatch.setattr(creation_scope, "_Data", lambda: data)
    assert recover_feat_spell_bindings(sheet, str(path), str(tmp_path))
    assert sheet["feats"][0]["grantedSpells"] == [
        {"spell": "longstrider", "resource": origin["name"]}]


def test_unpaired_archive_cannot_supply_binding(tmp_path, offline):
    from core.leveling.creation_picks import recover_feat_spell_bindings
    _archive(tmp_path, offline, tmp_path / "someone_else.json")
    sheet = {"feats": [{"name": NAME}]}
    assert not recover_feat_spell_bindings(sheet, str(tmp_path / "hero.json"), str(tmp_path))
    assert sheet == {"feats": [{"name": NAME}]}


@pytest.mark.parametrize("view", ["validator", "dm_flat", "dm_text"])
def test_all_context_views_keep_binding(view):
    from core.ai.character_sheet_compressor import format_flatlist
    from core.ai.conversation_utils import _feats_text
    from core.validation.compact_evidence import compact_sheet
    sheet = {"name": "Test Hero", "feats": [{"name": NAME, "grantedSpells": BINDING}]}
    text = {"validator": lambda: compact_sheet(sheet),
            "dm_flat": lambda: format_flatlist(sheet),
            "dm_text": lambda: _feats_text(sheet["feats"])}[view]()
    assert "grantedSpells" in text
    assert "longstrider" in text
    assert NAME in text


def test_updater_overrides_model_slot_payment_once(tmp_path, monkeypatch):
    from core.nql import resources
    from core.managers import effects_state
    updater = importlib.import_module("updates.update_character_info")
    sheet = json.loads((ROOT / "tests/fixtures/startup-authored-alden.json").read_text(
        encoding="utf-8"))["character"]
    sheet["feats"] = [{"name": NAME, "grantedSpells": BINDING,
                      "usage": {"current": 1, "max": 1, "refreshOn": "longRest"}}]
    sheet["spellcasting"]["spellSlots"]["level1"] = {"current": 2, "max": 2}
    path = tmp_path / "hero.json"
    path.write_text(json.dumps(sheet), encoding="utf-8")
    monkeypatch.setattr(updater, "get_character_path", lambda *args: str(path))
    monkeypatch.setattr(updater, "safe_json_load", lambda *args: {})
    monkeypatch.setattr(updater, "repair_character_data", copy.deepcopy)
    monkeypatch.setattr(updater, "load_conversation_history", lambda: [])
    monkeypatch.setattr(updater, "armor_contract_errors", lambda *args: [])
    monkeypatch.setattr(effects_state, "campaign_effects_migrated", lambda: False)
    monkeypatch.setattr(updater, "USAGE_TRACKING_AVAILABLE", False)
    calls, deltas = [], []

    def scripted(task, provider, **kwargs):
        calls.append(task)
        # Deliberately conflicting payments from the updater must both be replaced.
        content = json.dumps({"spellSlotDelta": {"level1": -1},
                              "featureUseDelta": {NAME: -2}})
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=content))], model="offline-script")

    def prepare(before, delta, *args, **kwargs):
        deltas.append(copy.deepcopy(delta))
        # Exercise actual resource arithmetic, not a fabricated engine result.
        outcome = resources.apply_deltas(copy.deepcopy(before), delta)
        assert outcome.ok, outcome.reason
        return delta, outcome.sheet, {"critical_warnings": [], "removed_fields": [],
                                      "schema_valid": True, "error_message": None}

    monkeypatch.setattr(updater, "capture_and_fanout", scripted)
    monkeypatch.setattr(updater, "prepare_character_delta", prepare)
    result = updater._update_character_info_unlocked(
        sheet["name"], "Casts the granted spell", "player", prepare_only=True,
        affects=["spellcasting"], casting_resource={"kind": "feature", "featureName": NAME})
    assert calls == ["T079"]
    assert deltas == [{"featureUseDelta": {NAME: -1}}]
    assert result["after"]["spellcasting"]["spellSlots"]["level1"]["current"] == 2
    assert result["after"]["feats"][0]["usage"]["current"] == 0
    assert json.loads(path.read_text(encoding="utf-8")) == sheet  # preparation does not commit
