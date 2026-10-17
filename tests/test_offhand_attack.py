"""R3: the Light-weapon Off-hand Attack (SRD 5.2.1 p89 Light, p88 Two-Weapon
Fighting) and Second Wind at full hit points. Offline, typed data only; the
fight windows run in the R3 gate."""
from core.combat.bonus_actions import (
    OFF_HAND_ATTACK,
    bonus_action_names,
    bonus_action_problem,
    holds_two_light_melee,
    off_hand_damage_rule,
)
from core.combat.resolver import resolution_from_event


def _weapon(slug, equipped=True, quantity=1):
    return {"item_name": slug.title(), "item_type": "weapon", "catalog_id": "itemdef:srd/%s" % slug,
            "equipped": equipped, "quantity": quantity}


def _fighter(*weapons, hp=12):
    return {"name": "Bram", "class": "Fighter", "level": 1, "hitPoints": hp, "maxHitPoints": 12,
            "equipment": list(weapons)}


def test_off_hand_listed_with_two_light_melee_weapons_in_hand():
    assert bonus_action_names(_fighter(_weapon("shortsword"), _weapon("scimitar"))) == ["Second Wind", OFF_HAND_ATTACK]
    assert bonus_action_names(_fighter(_weapon("shortsword"), _weapon("scimitar", equipped=False))) == ["Second Wind"]
    # A Longsword is not Light; a Light Hand Crossbow is not a melee weapon.
    assert not holds_two_light_melee(_fighter(_weapon("shortsword"), _weapon("longsword")))
    assert not holds_two_light_melee(_fighter(_weapon("shortsword"), _weapon("hand-crossbow")))
    # A stack row is one weapon in hand.
    assert not holds_two_light_melee(_fighter(_weapon("dagger", quantity=2)))
    assert holds_two_light_melee({"equipment": [_weapon("dagger"), _weapon("dagger")]})
    assert not holds_two_light_melee(None)


def test_second_wind_at_full_hit_points_is_refused_with_the_options():
    heal = {"featureName": "Second Wind", "targets": [{"combatantId": "a", "hpDelta": 7, "rolled": 6}]}
    two = _fighter(_weapon("shortsword"), _weapon("scimitar"))
    problem = bonus_action_problem(two, heal)
    assert "full hit points (12 of 12)" in problem and "'Off-hand Attack'" in problem
    # The d10 is never asked for it: refused while the intent still asks.
    assert "full hit points" in bonus_action_problem(two, {"featureName": "Second Wind"}, asking=True)
    alone = bonus_action_problem(_fighter(), heal)
    assert "no other bonus action" in alone
    assert bonus_action_problem(_fighter(hp=5), heal) is None
    assert bonus_action_problem(_fighter(hp=5), {"featureName": "Second Wind"}, asking=True) is None


def test_off_hand_damage_rule():
    style = {"classFeatures": [{"name": "Fighting Style: Two-Weapon Fighting"}]}
    assert off_hand_damage_rule({}, {"ability": "dexterity", "abilityModifier": 3}) == {
        "ability": "dexterity", "abilityModifier": 3, "modifierAdded": False, "removed": 3, "source": "SRD Light"}
    assert off_hand_damage_rule(style, {"ability": "dexterity", "abilityModifier": 3})["removed"] == 0
    # A negative modifier stays on the damage (SRD: "unless that modifier is negative").
    assert off_hand_damage_rule({}, {"ability": "strength", "abilityModifier": -1})["removed"] == 0


def _target(cid, before, after):
    return {"combatantId": cid, "hpBefore": before, "hpAfter": after, "statusAfter": "alive" if after else "dead"}


def test_replay_applies_the_off_hand_after_the_action():
    encounter = {"creatures": [{"combatantId": "b2", "name": "Bandit_2", "type": "enemy", "currentHitPoints": 11}]}
    event = {"eventId": "e1", "actorId": "p", "stateVersion": 1, "intent": {"action": "attack"}, "rolls": [],
             "resources": [], "outcome": {"kind": "attack", "targets": [_target("b2", 11, 11)]},
             "bonusAction": {"featureName": OFF_HAND_ATTACK, "order": "afterAction",
                             "outcome": {"targets": [_target("b2", 11, 5)]}, "resources": []}}
    assert resolution_from_event(encounter, {}, event)["creatureDeltas"]["b2"]["currentHitPoints"] == 5
    # R2's bonus actions (no order) still come first.
    event["bonusAction"].pop("order")
    assert resolution_from_event(encounter, {}, event)["creatureDeltas"]["b2"]["currentHitPoints"] == 11
