# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Armor class projection: the engine explains defense, code writes the sheet.

``project(sheet)`` builds a one-character world from the sheet's typed fields,
asks the engine for its ``defense`` explanation, and returns a copy of the sheet
with ``armorClass`` and the AC-target entries of ``equipment_effects`` rewritten
from that explanation. Nothing else on the sheet changes. No model is called.

Fail-forward: when the engine is unavailable, refuses the world, or the sheet
carries an equipped armor entry the typed fields cannot describe, the sheet is
returned unchanged with ``applied`` false and a reason. The caller logs it; it
never asks a model to guess the number instead.
"""
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import apply, genesis

AC_TARGET = "AC"
PROJECTION_LOCATION = "projection"


@dataclass
class Projection:
    sheet: Dict[str, Any]
    applied: bool
    reason: str = ""
    armor_class: Optional[int] = None
    previous_armor_class: Optional[int] = None
    explanation: Optional[Dict[str, Any]] = None
    gaps: List[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.applied and self.armor_class != self.previous_armor_class


def _equipped_armor_without_base(sheet: Dict[str, Any]) -> List[str]:
    names = []
    for entry in sheet.get("equipment") or []:
        if (isinstance(entry, dict) and entry.get("equipped") is True and entry.get("item_type") == "armor"
                and entry.get("armor_category") != "shield" and type(entry.get("ac_base")) is not int):
            names.append(str(entry.get("item_name", "")))
    return names


def _ac_entries(explanation: Dict[str, Any], names_by_id: Dict[str, str]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    recipe = explanation.get("recipe") or {}
    origin = (recipe.get("origin") or {}).get("item")
    if origin:
        name = names_by_id.get(origin, origin)
        base = recipe.get("base")
        entries.append({
            "name": f"{name} - Armor",
            "type": "other",
            "target": AC_TARGET,
            "value": base if type(base) is int else None,
            "description": f"Base AC {base} from {name}",
            "source": name,
        })
    for contribution in explanation.get("contributions") or []:
        source = (contribution.get("source") or {}).get("id")
        amount = contribution.get("amount")
        name = names_by_id.get(source, source or "engine")
        if type(amount) is not int:
            continue
        entries.append({
            "name": f"{name} - AC Bonus",
            "type": "bonus",
            "target": AC_TARGET,
            "value": amount,
            "description": f"{'+' if amount >= 0 else ''}{amount} AC from {name}",
            "source": name,
        })
    return entries


def project(sheet: Dict[str, Any], *, binary: Optional[str] = None) -> Projection:
    """Return the sheet with engine-owned AC fields rewritten, or unchanged with a reason."""
    previous = sheet.get("armorClass") if type(sheet.get("armorClass")) is int else None
    world = genesis.build_world([sheet], PROJECTION_LOCATION)
    # An entry typed armor with no ac_base is not modelled armor: genesis
    # treats it as a worn item with no defense and reports it in gaps. The
    # pre-update armor-field repair (T051, #357) is asked to classify such
    # entries; until it has, the projection uses the typed fields as they are.
    missing = _equipped_armor_without_base(sheet)
    if missing:
        world.gaps.append(f"equipped armor without ac_base projected as worn items with no defense: {missing}")
    cid = genesis.character_id(sheet)
    try:
        response = apply.genesis(world.source, explain=[{"character": cid, "stat": "defense"}], binary=binary)
    except apply.EngineUnavailable as error:
        return Projection(sheet, False, str(error), previous_armor_class=previous, gaps=world.gaps)
    if not response.get("ok"):
        detail = response.get("diagnostics") or response.get("fault") or response.get("error")
        return Projection(sheet, False, f"engine refused the world at {response.get('phase')}: {detail}",
                          previous_armor_class=previous, gaps=world.gaps)
    explanations = response.get("explain") or []
    if len(explanations) != 1 or type(explanations[0].get("effective")) is not int:
        return Projection(sheet, False, "engine returned no defense explanation", previous_armor_class=previous, gaps=world.gaps)
    explanation = explanations[0]
    names_by_id = dict(world.effect_names)
    for index, item_id in (world.item_ids.get(cid) or {}).items():
        entry = (sheet.get("equipment") or [])[index]
        names_by_id[item_id] = str(entry.get("item_name", item_id))

    result = copy.deepcopy(sheet)
    result["armorClass"] = explanation["effective"]
    kept = [e for e in result.get("equipment_effects") or []
            if not (isinstance(e, dict) and e.get("target") == AC_TARGET)]
    result["equipment_effects"] = kept + _ac_entries(explanation, names_by_id)
    return Projection(result, True, "", armor_class=explanation["effective"], previous_armor_class=previous,
                      explanation=explanation, gaps=world.gaps)
