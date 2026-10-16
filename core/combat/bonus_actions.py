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
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from core.leveling.tables import _feature_key, class_key, tables

# The bonus actions r0 resolves (owner Q3: class features only). Steady Aim
# is a Bonus Action in the SRD too, but its advantage is not resolved yet.
R0_FEATURES = ("Second Wind", "Cunning Action")
CUNNING_ACTION_OPTIONS = ("dash", "disengage", "hide")


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
    return names


def bonus_name_refused(sheet: Optional[Dict[str, Any]], bonus: Any) -> bool:
    """True when a declared bonusAction names no feature in the actor's
    bonusActionNames (the correction then lists the names)."""
    return not isinstance(bonus, dict) or bonus.get("featureName") not in bonus_action_names(sheet)


def bonus_action_problem(sheet: Optional[Dict[str, Any]], bonus: Any) -> Optional[str]:
    """Why a declared bonusAction cannot be ruled as given, or None."""
    names = bonus_action_names(sheet)
    if not isinstance(bonus, dict):
        return "bonusAction must be one object"
    name = bonus.get("featureName")
    if name not in names:
        return ("bonusAction.featureName must be one of this actor's bonusActionNames (%s)"
                % (", ".join(repr(n) for n in names) or "none: this actor has no bonus action to take"))
    if name == "Cunning Action" and bonus.get("option") not in CUNNING_ACTION_OPTIONS:
        return "Cunning Action's bonusAction.option must be one of %s" % ", ".join(
            repr(o) for o in CUNNING_ACTION_OPTIONS)
    if name == "Second Wind" and _heal_target(bonus) is None:
        return ("Second Wind's bonusAction heals its user: targets [{combatantId: the actor, hpDelta, rolled}], "
                "rolled the d10 face (1-10); ask the player's d10 first with the intent's requiresPlayerInput")
    return None


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

