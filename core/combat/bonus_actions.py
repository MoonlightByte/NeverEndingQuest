# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""R2 (owner, 2026-10-16): one typed Bonus Action beside an actor's Action.

An intent may carry ``bonusAction``: a class feature the actor's sheet has
whose SRD activation is a Bonus Action. Which features those are is typed
data, ``feature_activation`` in data/srd/progression.json (the SRD sentence
and page for each); the player's words are never read. r0 resolves two of
them: Second Wind (a heal from its own use) and Cunning Action (Dash,
Disengage or Hide). The bonus action resolves before the Action, as its own
adjudicated ruling, and its outcome rides on the actor's one event.

R3 (owner, 2026-10-16): the Off-hand Attack, SRD 5.2.1 p89 Light: "When you
take the Attack action on your turn and attack with a Light weapon, you can
make one extra attack as a Bonus Action later on the same turn. That extra
attack must be made with a different Light weapon, and you don't add your
ability modifier to the extra attack's damage unless that modifier is
negative." p88, Two-Weapon Fighting (Fighting Style feat): "you can add your
ability modifier to the damage of that attack". It is listed when the sheet
holds two Light melee weapons (typed equipment rows and the catalog's Light
property) and resolves after the Action (owner: the SRD's order). Second Wind
at full hit points restores nothing and is refused, naming the other options.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from core.leveling.tables import _feature_key, class_key, tables

# The bonus actions r0 resolves (owner Q3: class features only). Steady Aim
# is a Bonus Action in the SRD too, but its advantage is not resolved yet.
R0_FEATURES = ("Second Wind", "Cunning Action")
CUNNING_ACTION_OPTIONS = ("dash", "disengage", "hide")
# R3: the Light property's extra attack, and the style that keeps its modifier.
OFF_HAND_ATTACK = "Off-hand Attack"
TWO_WEAPON_STYLE_FEATURE = "Fighting Style: Two-Weapon Fighting"


def _level(sheet: Dict[str, Any]) -> int:
    level = (sheet or {}).get("level")
    return level if type(level) is int and level > 0 else 0


def bonus_action_names(sheet: Optional[Dict[str, Any]]) -> List[str]:
    """The r0 bonus actions the sheet's class has at its level, as the typed
    feature_activation records them (activation 'bonusAction'), in r0 order.
    A use pool's remaining uses are the resolver's to refuse, as today."""
    cls = class_key(sheet or {})
    level = _level(sheet or {})
    if cls is None or level < 1:
        return []
    record = tables()["classes"][cls]
    activation = record.get("feature_activation") or {}
    gained = {
        _feature_key(row)
        for lv in range(1, level + 1)
        for row in (record.get("features_by_level") or {}).get(str(lv), [])
    }
    names = []
    for name in R0_FEATURES:
        entry = activation.get(name)
        if not isinstance(entry, dict) or entry.get("activation") != "bonusAction":
            continue
        rows = [name] + list(entry.get("table_names") or [])
        if any(_feature_key(row) in gained for row in rows):
            names.append(name)
    return names + ([OFF_HAND_ATTACK] if holds_two_light_melee(sheet) else [])


def holds_two_light_melee(sheet: Optional[Dict[str, Any]]) -> bool:
    """R3: two equipped weapon rows whose catalog entries are Light melee
    weapons (typed equipment, the catalog's Light property; a stack row is one
    weapon in hand, as the engine wears one)."""
    from core.nql import item_catalog

    held = 0
    for row in (sheet or {}).get("equipment") or []:
        if not isinstance(row, dict) or row.get("equipped") is not True:
            continue
        entry = item_catalog.entry(row.get("catalog_id"))
        weapon = entry.get("weapon") if isinstance(entry, dict) else None
        if isinstance(weapon, dict) and weapon.get("kind") == "Melee" and any(
                isinstance(p, dict) and p.get("name") == "Light" for p in weapon.get("properties") or []):
            held += 1
    return held >= 2


def bonus_name_refused(sheet: Optional[Dict[str, Any]], bonus: Any) -> bool:
    """True when a declared bonusAction names no feature in the actor's
    bonusActionNames (the correction then lists the names)."""
    if isinstance(bonus, dict) and "item" in bonus:
        return False
    return not isinstance(bonus, dict) or bonus.get("featureName") not in bonus_action_names(sheet)


def bonus_action_problem(sheet: Optional[Dict[str, Any]], bonus: Any, intent: Optional[Dict[str, Any]] = None,
                         encounter: Optional[Dict[str, Any]] = None, asking: bool = False,
                         actor_id: Optional[str] = None) -> Optional[str]:
    """Why a declared bonusAction cannot be ruled as given, or None. With
    ``intent`` and ``encounter`` the Off-hand Attack is checked against the
    Action and its target too; ``asking`` (the intent still asks the player
    for a roll) leaves out the checks that need the answer."""
    names = bonus_action_names(sheet)
    if not isinstance(bonus, dict):
        return "bonusAction must be one object"
    if "item" in bonus:
        return item_bonus_problem(sheet, bonus, encounter)
    name = bonus.get("featureName")
    if name not in names:
        return ("bonusAction.featureName must be one of this actor's bonusActionNames (%s)"
                % (", ".join(repr(n) for n in names) or "none: this actor has no bonus action to take"))
    if name == "Second Wind" and at_full_hit_points(sheet):
        others = bonus_action_options(sheet, bonus)
        return ("Second Wind restores hit points and %s is at full hit points (%s of %s): it is not taken. "
                "Leave bonusAction out%s"
                % ((sheet or {}).get("name") or "the actor", sheet.get("hitPoints"), sheet.get("maxHitPoints"),
                   ", or use one of this actor's other bonus actions: %s" % ", ".join(repr(n) for n in others)
                   if others else " (this actor has no other bonus action)"))
    if name == OFF_HAND_ATTACK:
        return off_hand_problem(sheet, bonus, intent, encounter, actor_id)
    if asking:
        return None
    if name == "Cunning Action" and bonus.get("option") not in CUNNING_ACTION_OPTIONS:
        return "Cunning Action's bonusAction.option must be one of %s" % ", ".join(
            repr(o) for o in CUNNING_ACTION_OPTIONS)
    if name == "Second Wind" and _heal_target(bonus) is None:
        return ("Second Wind's bonusAction heals its user: targets [{combatantId: the actor, hpDelta, rolled}], "
                "rolled the d10 face (1-10); ask the player's d10 first with the intent's requiresPlayerInput")
    return None


def at_full_hit_points(sheet: Optional[Dict[str, Any]]) -> bool:
    """The sheet's typed hit points are at their maximum."""
    current, top = (sheet or {}).get("hitPoints"), (sheet or {}).get("maxHitPoints")
    return type(current) is int and type(top) is int and current >= top


def bonus_action_options(sheet: Optional[Dict[str, Any]], bonus: Any) -> List[str]:
    """The actor's bonusActionNames other than the refused one."""
    refused = bonus.get("featureName") if isinstance(bonus, dict) else None
    return [n for n in bonus_action_names(sheet) if n != refused]


def _items_differ(first: List[Any], second: List[Any]) -> bool:
    """One item of ``first`` and a different item of ``second`` exist."""
    return any(a != b for a in first for b in second)


def off_hand_problem(sheet: Optional[Dict[str, Any]], bonus: Dict[str, Any], intent: Optional[Dict[str, Any]],
                     encounter: Optional[Dict[str, Any]], actor_id: Optional[str] = None) -> Optional[str]:
    """Why the declared Off-hand Attack cannot be taken as given, or None: the
    Action is an Attack with a Light melee weapon in hand, the bonus swing is
    a different Light melee weapon in hand, and the target is hostile."""
    from core.managers.combat_state import combatant_by_id, is_combatant_targetable, is_hostile
    from core.nql import hands

    from core.combat.resolver import attack_row, row_refs, attack_family, json_ref_list

    rows = hands.light_melee_rows(sheet)
    if rows is None:
        return "the Off-hand Attack needs the rules engine, which is unavailable now: leave bonusAction out"
    # K1: both weapons are the rows their abilityRow names (the actor's own
    # list); the Light rows are then indexed by those rows' own names (code
    # data against code data), never by the ability text.
    actor_id = (intent or {}).get("actorId") or actor_id
    main_row = attack_row(sheet, (intent or {}).get("abilityRow"), actor_id) if intent is not None else None
    main = (main_row or {}).get("name")

    def listed(names):
        return json_ref_list(row_refs(sheet, actor_id, (attack_family(sheet),), lambda e: e.get("name") in names))

    if intent is not None and (intent.get("action") != "attack" or main not in rows):
        return ("the Off-hand Attack follows this turn's Attack action made with a Light melee weapon in hand "
                "(SRD Light): the Action must be action 'attack' with abilityRow the rowRef of one of %s, or leave "
                "bonusAction out" % listed(set(rows)))
    main_items = rows[main]["items"] if main in rows else []
    others = sorted(n for n in rows if intent is None or _items_differ(main_items, rows[n]["items"]))
    bonus_row = attack_row(sheet, bonus.get("abilityRow"), actor_id) if actor_id is not None else None
    if (bonus_row or {}).get("name") not in others:
        return ("Off-hand Attack's bonusAction.abilityRow is the attack rowRef of the other Light weapon in hand: "
                "one of %s" % listed(set(others)))
    if encounter is not None:
        target = combatant_by_id(encounter, bonus.get("targetId"))
        if target is None or not is_hostile(target) or not is_combatant_targetable(target):
            return "Off-hand Attack's bonusAction.targetId is the combatantId of one hostile creature"
    return None


def off_hand_damage_rule(sheet: Optional[Dict[str, Any]], row: Dict[str, Any]) -> Dict[str, Any]:
    """The Off-hand Attack's damage modifier rule (SRD Light; the Two-Weapon
    Fighting style keeps it): the ability modifier taken off the row's damage
    bonus, 0 when it is kept or negative."""
    modifier = int(row.get("abilityModifier") or 0)
    style = any(isinstance(f, dict) and f.get("name") == TWO_WEAPON_STYLE_FEATURE
                for f in (sheet or {}).get("classFeatures") or [])
    removed = 0 if style or modifier < 0 else modifier
    return {"ability": row.get("ability"), "abilityModifier": modifier, "modifierAdded": removed == 0,
            "removed": removed, "source": TWO_WEAPON_STYLE_FEATURE if style else "SRD Light"}


def _heal_target(bonus: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Second Wind's heal: the first target with a positive hpDelta or a
    rolled d10 face (code sets the heal from rolled, #881), else None."""
    for target in bonus.get("targets") or []:
        if not isinstance(target, dict):
            continue
        if (type(target.get("hpDelta")) is int and target["hpDelta"] > 0) or (
                type(target.get("rolled")) is int and target["rolled"] > 0):
            return target
    return None


def bonus_subintent(intent: Dict[str, Any], bonus: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    """The adjudicated ruling the bonus action resolves as, before the Action.
    Second Wind spends one of its own uses and heals its user (the #881
    formula: the rolled d10 plus the Fighter level); Cunning Action takes its
    option with no outcome of its own."""
    actor_id = intent.get("actorId")
    name = bonus.get("featureName")
    sub = {"actorId": actor_id, "mode": "adjudicated", "ability": name, "targets": [], "resources": [],
           "effects": [], "description": str(bonus.get("description") or name)}
    if name == "Second Wind":
        heal = _heal_target(bonus) or {}
        rolled = heal.get("rolled") if type(heal.get("rolled")) is int else bonus.get("rolled")
        declared = heal.get("hpDelta")
        if not (type(declared) is int and declared > 0):
            # Only the face was given: it stands as the declared heal, and the
            # #881 formula sets the heal to the face plus the Fighter level.
            declared = rolled
        target = {"combatantId": actor_id, "hpDelta": declared}
        if type(rolled) is int:
            target["rolled"] = rolled
        sub.update(action="Second Wind", featureName="Second Wind", targets=[target],
                   resources=[{"owner": actor_name, "kind": "featureUse", "name": "Second Wind", "delta": -1}])
    else:
        sub["action"] = bonus.get("option")
    return sub


def drop_bonus_spend(intent: Dict[str, Any], record: Dict[str, Any], actor_name: str) -> List[Dict[str, Any]]:
    """The bonus action's own use listed again on the Action's resources is the
    same spend, already made by the bonus action: it is removed from the
    Action (typed owner, kind and name) and returned for the journal."""
    spent = {(r.get("owner"), r.get("kind"), r.get("name")) for r in record.get("resources") or []
             if isinstance(r, dict)}
    kept, dropped = [], []
    for resource in intent.get("resources") or []:
        key = (resource.get("owner"), resource.get("kind"), resource.get("name")) if isinstance(resource, dict) else None
        (dropped if key in spent and key[0] == actor_name else kept).append(resource)
    if dropped:
        intent["resources"] = kept
    return dropped


def bonus_record(bonus: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
    """The typed record of a resolved bonus action, kept on the actor's event:
    what was used, its outcome targets and resources (absolute after values,
    so a replay converges) and any normalization."""
    record = {"featureName": bonus.get("featureName"), "description": (event.get("intent") or {}).get("description")}
    if bonus.get("option"):
        record["option"] = bonus["option"]
    record["outcome"] = {"targets": deepcopy((event.get("outcome") or {}).get("targets") or [])}
    record["resources"] = deepcopy(event.get("resources") or [])
    if event.get("normalizations"):
        record["normalizations"] = deepcopy(event["normalizations"])
    if event.get("rolls"):
        record["rolls"] = deepcopy(event["rolls"])
    return record



def item_bonus_problem(sheet, bonus, encounter):
    """P3/r3: only owned stock and present living targets; reach stays agentic."""
    from core.nql.item_use import resolve_row, use_data
    from core.managers.combat_state import combatant_by_id, normalize_status
    if set(bonus) != {"item", "targetId"}:
        return "item bonusAction must contain only item and targetId; one Bonus Action per turn"
    found = resolve_row(sheet, bonus["item"])
    if found is None:
        return "item bonusAction requires one owned item by nqlId or catalog_id, never a name"
    row = found[1]
    if type(row.get("quantity")) is not int or row["quantity"] <= 0:
        return "You have no %s left. Nothing was spent." % row.get("item_name", "item")
    if use_data(row) is None:
        return "item has no typed bonus-action use"
    target = combatant_by_id(encounter or {}, bonus.get("targetId"))
    if target is None or normalize_status(target.get("status")) not in ("alive", "unconscious"):
        return "item bonusAction targetId must name a present, living encounter participant"
    return None


def resolve_item_bonus(encounter, characters, actor, intent, bonus, event_id):
    """Engine-owned heal and spend, as one replayable bonus-action event."""
    from core.nql import item_use
    from core.combat.resolver import resolution_from_event, apply_resolution
    from core.managers.combat_state import combatant_by_id
    sheet = characters[actor["name"]]
    target = combatant_by_id(encounter, bonus["targetId"])
    target_sheet = deepcopy(characters.get(target["name"]) or target)
    target_sheet.update(hitPoints=target["currentHitPoints"], maxHitPoints=target["maxHitPoints"])
    owner_sheet = deepcopy(sheet)
    owner_sheet["hitPoints"] = actor["currentHitPoints"]
    if target["combatantId"] == actor["combatantId"]:
        target_sheet = owner_sheet
    result = item_use.heal(owner_sheet, target_sheet, bonus["item"])
    row = item_use.resolve_row(sheet, bonus["item"])[1]
    event = {"eventId": event_id + "-B", "actorId": actor["combatantId"],
             "stateVersion": intent["stateVersion"],
             "intent": {"action": "useItem", "item": deepcopy(bonus["item"])},
             "outcome": {"kind": "healing", "targets": [{"combatantId": target["combatantId"],
                 "hpBefore": target["currentHitPoints"], "hpAfter": result["hitPoints"], "statusAfter": "alive"}]},
             "resources": [{"owner": actor["name"], "kind": "item", "name": row["item_name"],
                 "item": deepcopy(bonus["item"]), "delta": -1, "before": row["quantity"],
                 "after": result["quantity"], "engine": True}],
             "rolls": result["rolls"], "effects": []}
    updated, sheets = apply_resolution(encounter, characters, resolution_from_event(encounter, characters, event))
    record = {"item": deepcopy(bonus["item"]), "targetId": bonus["targetId"],
              "outcome": event["outcome"], "resources": event["resources"], "rolls": event["rolls"]}
    return record, updated, sheets


def item_bonus_refusal(sheet, bonus):
    """The existing #968 player-choice record for absent consumable stock."""
    from core.nql.item_use import resolve_row
    if not isinstance(bonus, dict) or not isinstance(bonus.get("item"), dict):
        return None
    found = resolve_row(sheet, bonus["item"])
    row = found[1] if found else {}
    quantity = row.get("quantity", 0)
    if type(quantity) is int and quantity > 0:
        return None
    return {"owner": (sheet or {}).get("name"), "kind": "item", "name": row.get("item_name", "requested item"),
            "item": deepcopy(bonus["item"]), "before": quantity, "need": 1, "max": None,
            "actor": (sheet or {}).get("name")}
