"""#1331 approved P/R rows: typed fixtures, real local engine, no provider calls."""
from copy import deepcopy
import json
from pathlib import Path
import socket

import pytest

from core.ai import srd_spell_attacks
from core.combat.bonus_actions import bonus_action_problem
from core.combat.pipeline import CombatIntentError, resolve_claimed_window
from core.combat import resolver as r
from core.nql import item_use


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("offline rows cannot call a provider")
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(item_use.checks, "fresh_seed", lambda: (1, 2))


def world(quantity=1):
    sheet = {"name": "Mira", "class": "Wizard", "level": 1, "hitPoints": 4, "maxHitPoints": 8,
             "armorClass": 12, "speed": 30, "abilities": {"dexterity": 14, "intelligence": 17},
             "spellcasting": {"ability": "intelligence", "spellAttackBonus": 5,
                 "spells": {"cantrips": ["Ray of Frost"], "level1": ["Magic Missile"]},
                 "spellSlots": {"level1": {"current": 1, "max": 2}}},
             "equipment": [{"item_name": "Potion of Healing", "catalog_id": "itemdef:srd/potion-of-healing",
                            "nql_id": "item:potion:mira", "quantity": quantity}]}
    encounter = {"encounterId": "E", "combatState": {"revision": 1, "round": 1}, "creatures": [
        {"combatantId": "p", "name": "Mira", "type": "player", "faction": "party", "status": "alive",
         "currentHitPoints": 4, "maxHitPoints": 8, "armorClass": 12},
        {"combatantId": "g", "name": "Gorvek", "type": "enemy", "faction": "hostile", "status": "alive",
         "currentHitPoints": 27, "maxHitPoints": 27, "armorClass": 15}]}
    return encounter, {"Mira": sheet, "Gorvek": {"name": "Gorvek", "speed": 30}}


def cast():
    return {"actorId": "p", "stateVersion": 1, "mode": "adjudicated", "action": "cast",
            "ability": "Ray of Frost", "targetId": "g", "targets": [], "resources": [],
            "bonusAction": {"item": {"nqlId": "item:potion:mira"}, "targetId": "p"}}


def phase(encounter, characters, intent, face, damage=None):
    spell = r.player_spell_attack_entry(encounter, characters, intent)
    assert spell is not None
    record = r.open_player_spell_attack(encounter, characters, intent, spell)
    record["faces"]["attack"] = [face]
    entry = r.weapon_attack_sheet_entry(encounter, characters, record)
    hit, critical, *_ = r.player_weapon_attack_score(encounter, characters, record, entry)
    record.update(critical=critical, ready=True)
    if damage is not None:
        record["faces"]["damage"] = damage
    return record, entry, hit


def window(encounter, characters, intent, record=None):
    pending = {"baseRevision": 1, "round": 1, "turnId": "turn", "actorIds": ["p"]}
    if record:
        pending["weaponAttack"] = record
    return resolve_claimed_window(encounter, characters, pending,
                                  {"stateVersion": 1, "intents": [intent]}, r.DeterministicRollSource({}))


def test_p1_p3a_heal_before_cantrip_and_durable_replay():
    encounter, characters = world()
    intent = cast()
    record, _, hit = phase(encounter, characters, intent, 6)
    assert not hit
    result = window(encounter, characters, intent, record)
    event = result[0][0]
    bonus = event["bonusAction"]
    assert bonus["resources"][0]["before"] == 1 and bonus["resources"][0]["after"] == 0
    roll = bonus["rolls"][0]
    assert roll["faces"] == [1, 1] and roll["bonus"] == 2 and roll["engine_drawn"]
    assert bonus["outcome"]["targets"][0]["hpAfter"] == 8
    after, sheets = r.apply_resolution(encounter, characters, r.resolution_from_event(encounter, characters, event))
    assert sheets["Mira"]["hitPoints"] == 8 and sheets["Mira"]["equipment"][0]["quantity"] == 0
    assert sheets["Mira"]["equipment"][0]["nql_id"] == "item:potion:mira"
    assert len(sheets["Mira"]["equipment"]) == 1
    assert item_use.available(sheets["Mira"]) == []
    assert after["creatures"][1]["currentHitPoints"] == 27
    again, sheets2 = r.apply_resolution(after, sheets, r.resolution_from_event(after, sheets, event))
    assert sheets2 == sheets and again == after


def test_p2_no_stock_refuses_without_staging():
    encounter, characters = world(0)
    before = deepcopy((encounter, characters))
    with pytest.raises(CombatIntentError, match="Nothing was spent") as error:
        window(encounter, characters, cast())
    assert error.value.feedback["playerResourceRefusal"][0]["before"] == 0
    assert (encounter, characters) == before


def test_p3b_ally_heal_and_owner_spend():
    encounter, characters = world()
    ally = deepcopy(characters["Mira"])
    ally.update(name="Ally", hitPoints=2, equipment=[])
    characters["Ally"] = ally
    encounter["creatures"].append({"combatantId": "a", "name": "Ally", "type": "npc", "faction": "party",
                                  "currentHitPoints": 2, "maxHitPoints": 8, "status": "alive"})
    intent = cast()
    intent.update(action="dodge", ability="Dodge", targets=[])
    intent["bonusAction"]["targetId"] = "a"
    result = window(encounter, characters, intent)
    event = result[0][0]
    _, sheets = r.apply_resolution(encounter, characters, r.resolution_from_event(encounter, characters, event))
    assert sheets["Ally"]["hitPoints"] == 6 and sheets["Mira"]["hitPoints"] == 4
    assert sheets["Mira"]["equipment"][0]["quantity"] == 0


@pytest.mark.parametrize("status", ["missing", "dead", "defeated"])
def test_p3c_invalid_target_no_mutation(status):
    encounter, characters = world()
    intent = cast()
    intent["bonusAction"]["targetId"] = "missing" if status == "missing" else "g"
    if status != "missing":
        encounter["creatures"][1].update(status=status, currentHitPoints=0)
    before = deepcopy((encounter, characters))
    with pytest.raises(CombatIntentError, match="present, living"):
        window(encounter, characters, intent)
    assert (encounter, characters) == before


def test_p4_p7_second_bonus_and_name_reference_refused():
    encounter, characters = world()
    bonus = cast()["bonusAction"]
    assert "one Bonus Action" in bonus_action_problem(characters["Mira"], dict(bonus, featureName="Second Wind"), encounter=encounter)
    assert "never a name" in bonus_action_problem(characters["Mira"], dict(bonus, item="Potion of Healing"), encounter=encounter)


def test_p6_potion_and_leveled_spell_both_resolve():
    encounter, characters = world()
    intent = cast()
    intent.update(ability="Magic Missile", targets=[{"combatantId": "g", "hpDelta": -6}],
                  resources=[{"owner": "Mira", "kind": "spellSlot", "name": "level1", "delta": -1}])
    event = window(encounter, characters, intent)[0][0]
    after, sheets = r.apply_resolution(encounter, characters, r.resolution_from_event(encounter, characters, event))
    assert sheets["Mira"]["hitPoints"] == 8 and sheets["Mira"]["equipment"][0]["quantity"] == 0
    assert sheets["Mira"]["spellcasting"]["spellSlots"]["level1"]["current"] == 0
    assert after["creatures"][1]["currentHitPoints"] == 21


def test_r1_recorded_attack_miss_has_no_damage_or_rider():
    encounter, characters = world()
    intent = cast()
    record, entry, hit = phase(encounter, characters, intent, 6)
    assert r.player_weapon_attack_dice(record, entry) == (1, 20) and not hit
    result = r.resolve_player_spell_attack(encounter, characters, intent, record, "E-R1-turn-A1", r.DeterministicRollSource({}))
    assert not result["violations"] and not result["effectOps"]
    assert result["event"]["outcome"]["damage"] == 0
    assert result["event"]["outcome"]["spellAttack"]["engine"] is True


@pytest.mark.parametrize("model_name", ["Ray of Frost", "Frost slow"])
def test_r2_r4_rider_once_and_expires_in_ongoing_encounter(model_name):
    encounter, characters = world()
    intent = cast()
    intent["effects"] = [{"op": "add", "combatantId": "g", "applyOn": "hit",
                          "effect": {"name": model_name, "modifiers": [{"stat": "speed", "value": -20}]}}]
    record, entry, hit = phase(encounter, characters, intent, 15, 5)
    assert hit and len(intent["effects"]) == 1
    record["phase"] = "damage"
    assert r.player_weapon_attack_dice(record, entry) == (1, 8)
    result = r.resolve_player_spell_attack(encounter, characters, intent, record, "E-R1-turn-A1", r.DeterministicRollSource({}))
    assert not result["violations"]
    after, sheets = r.apply_resolution(encounter, characters, result)
    target = after["creatures"][1]
    assert target["currentHitPoints"] == 22 and len(target["activeEffects"]) == 1
    effect = target["activeEffects"][0]
    assert effect["modifiers"] == [{"stat": "speed", "value": -10}]
    assert effect["roundsRemaining"] == 1
    assert r._effective_combatant_sheet(after, sheets, target)["speed"] == 20
    assert not r.plan_effect_ticks(sheets, "end_of_round", after, created_in_round=1)
    ticks = r.plan_effect_ticks(sheets, "end_of_round", after, created_in_round=2)
    expired = r.apply_encounter_effect_ticks(after, ticks)
    assert expired["creatures"][1]["activeEffects"] == []
    assert expired["creatures"][1]["currentHitPoints"] == 22
    assert r._effective_combatant_sheet(expired, sheets, expired["creatures"][1])["speed"] == 30
    assert not r.plan_effect_ticks(sheets, "end_of_round", expired, created_in_round=3)


@pytest.mark.parametrize("face,critical,hit", [(20, True, True), (1, False, False)])
def test_r3_critical_and_natural_one(face, critical, hit):
    encounter, characters = world()
    record, entry, actual = phase(encounter, characters, cast(), face)
    assert actual == hit and record["critical"] == critical
    record["phase"] = "damage"
    assert r.player_weapon_attack_dice(record, entry) == (2 if critical else 1, 8)


def test_r5_excluded_and_g1_citations():
    for name in ("Chill Touch", "Shocking Grasp"):
        assert srd_spell_attacks.lookup(name)[0] == "unrecorded"
    entry = srd_spell_attacks.lookup("Ray of Frost")[1]
    assert entry["source"] == "SRD 5.2.1 p.157" and entry["_srd_attribution"]
    use = item_use.use_data(world()[1]["Mira"]["equipment"][0])
    assert use["source"] == "SRD 5.2.1 p.95" and use["_srd_attribution"]
    assert "reach_ft" not in use
    assert use["heal"] == {"count": 2, "sides": 4, "bonus": 2}


def test_r6_untyped_rider_duration_refused(tmp_path, monkeypatch):
    data = deepcopy(srd_spell_attacks.load_spell_attacks())
    del data["attacks"]["ray_of_frost"]["onHit"][0]["effect"]["roundsRemaining"]
    path = tmp_path / "attacks.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(srd_spell_attacks, "ATTACKS_PATH", path)
    srd_spell_attacks.load_spell_attacks.cache_clear()
    with pytest.raises(srd_spell_attacks.SpellAttackDataError, match="typed round duration"):
        srd_spell_attacks.load_spell_attacks()
    srd_spell_attacks.load_spell_attacks.cache_clear()


def test_r3_cover_and_character_level_scaling():
    encounter, characters = world()
    assert phase(encounter, characters, cast(), 10)[2]
    encounter["creatures"][1]["armorClass"] = 17
    assert not phase(encounter, characters, cast(), 10)[2]
    for level, count in [(1, 1), (5, 2), (11, 3), (17, 4)]:
        characters["Mira"]["level"] = level
        entry = r.player_spell_attack_entry(encounter, characters, cast())
        assert entry["damageDice"] == "%dd8" % count
