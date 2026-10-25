# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Armor class projection: the engine explains defense, code writes the sheet.

``project(sheet)`` builds a one-character world from the sheet's typed fields,
asks the engine for its ``defense`` explanation, and returns a copy of the sheet
with ``armorClass`` and the AC-target entries of ``equipment_effects`` rewritten
from that explanation. Engine status also supplies the existing derived totals;
the returned status records their provenance. No model is called.

Fail-forward: when the engine is unavailable, refuses the world, or the sheet
carries an equipped armor entry the typed fields cannot describe, the sheet is
returned unchanged with ``applied`` false and a reason. The caller logs it; it
never asks a model to guess the number instead.
"""
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.nql import apply, class_conditions, genesis, stats

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
    notes: List[str] = field(default_factory=list)  # genesis notes (NUM-H3b); they never block the projection
    status: Optional[Dict[str, Any]] = None

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


def unmodelled_armor(sheet: Dict[str, Any]) -> List[str]:
    """Item names of the equipped armor rows the projection cannot model (no
    integer ac_base): the rows project() reports in its gaps."""
    return _equipped_armor_without_base(sheet)


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
    # #1322: the engine chose a live set effect's recipe (Mage Armor). Named
    # like worn armor: its base, with the ability its term reads.
    # #1408: the instance is the holder's own (scoped for a repeat holder of a shared effectId).
    # #1433: a class formula's recipe (Draconic Resilience) is named from its typed record.
    instance = genesis.ac_set_instance_id(recipe.get("name"))
    effect_name = names_by_id.get(instance) if instance else class_conditions.recipe_feature(recipe.get("name"))
    if effect_name:
        base = recipe.get("base")
        abilities = [str((t.get("term") or {}).get("stat") or "").capitalize() for t in recipe.get("terms") or []
                     if isinstance(t, dict) and t.get("active") is True]
        entries.append({
            "name": f"{effect_name} - Armor",
            "type": "other",
            "target": AC_TARGET,
            "value": base if type(base) is int else None,
            "description": f"Base AC {base}{''.join(' + ' + a for a in abilities)} from {effect_name}",
            "source": effect_name,
        })
    # NUM-H3b: an active Unarmored Defense term of the defense derive (a recipe
    # term whose typed requires names feature:unarmored-defense:<class>) is
    # named on the sheet, with the engine's exact amount and its ability.
    for term in recipe.get("terms") or []:
        spec = term.get("term") if isinstance(term, dict) else None
        if not (isinstance(spec, dict) and term.get("active") is True
                and str(spec.get("requires") or "").startswith(class_conditions.UNARMORED_DEFENSE_PREFIX)):
            continue
        try:
            amount = int(str(term.get("exact")))
        except ValueError:
            continue
        ability = str(spec.get("stat") or "").capitalize()
        entries.append({
            "name": "Unarmored Defense - AC Bonus",
            "type": "bonus",
            "target": AC_TARGET,
            "value": amount,
            "description": f"{'+' if amount >= 0 else ''}{amount} AC from Unarmored Defense ({ability})",
            "source": "Unarmored Defense",
        })
    # #1434: a floor (Barkskin) that set the total; one that did not apply is not named.
    for bound in explanation.get("bounds") or []:
        if not (isinstance(bound, dict) and bound.get("bound") == "at_least" and bound.get("applied") is True
                and type(bound.get("amount")) is int):
            continue
        name = names_by_id.get(bound.get("instance"))
        if not name:
            continue
        entries.append({
            "name": f"{name} - AC Floor",
            "type": "other",
            "target": AC_TARGET,
            "value": bound["amount"],
            "description": f"AC {bound['amount']} from {name} (it can't be lower)",
            "source": name,
        })
    for contribution in explanation.get("contributions") or []:
        source = (contribution.get("source") or {}).get("id")
        amount = contribution.get("amount")
        name = names_by_id.get(source, source or "engine")
        member = (contribution.get("equipment_origin") or {}).get("member")
        if member == genesis.DEFENSE_STYLE_MEMBER:
            name = genesis.DEFENSE_STYLE_FEATURE  # the engine's +1 comes from the style, worn through the armor
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
    from core.leveling import fighting_style  # lazy, as the projection's other table readers
    style_note = fighting_style.pending_note(sheet)
    if style_note:
        world.notes.append(style_note)  # #760: the saved style waits for a level-up; AC is untouched
    # An entry typed armor with no ac_base is not modelled armor: genesis
    # treats it as a worn item with no defense and reports it in gaps. The
    # pre-update armor-field repair (T051, #357) is asked to classify such
    # entries; until it has, the projection uses the typed fields as they are.
    missing = _equipped_armor_without_base(sheet)
    if missing:
        world.gaps.append(f"equipped armor without ac_base projected as worn items with no defense: {missing}")
    cid = genesis.character_id(sheet)
    try:
        response = apply.genesis(world.source, explain=[{"character": cid, "stat": "defense"}], status=[cid], binary=binary)
    except apply.EngineUnavailable as error:
        return Projection(sheet, False, str(error), previous_armor_class=previous, gaps=world.gaps, notes=world.notes)
    if not response.get("ok"):
        detail = response.get("diagnostics") or response.get("fault") or response.get("error")
        return Projection(sheet, False, f"engine refused the world at {response.get('phase')}: {detail}",
                          previous_armor_class=previous, gaps=world.gaps, notes=world.notes)
    explanations = response.get("explain") or []
    if len(explanations) != 1 or type(explanations[0].get("effective")) is not int:
        return Projection(sheet, False, "engine returned no defense explanation", previous_armor_class=previous, gaps=world.gaps, notes=world.notes)
    explanation = explanations[0]
    names_by_id = dict(world.effect_names)
    for index, item_id in (world.item_ids.get(cid) or {}).items():
        entry = (sheet.get("equipment") or [])[index]
        names_by_id[item_id] = str(entry.get("item_name", item_id))

    result = copy.deepcopy(sheet)
    result["armorClass"] = explanation["effective"]
    projected_status = None
    for status in response.get("status") or []:
        if isinstance(status.get("character"), dict) and status["character"].get("id") == cid:
            stats.store(result, status)
            projected_status = copy.deepcopy(status)
    kept = [e for e in result.get("equipment_effects") or []
            if not (isinstance(e, dict) and e.get("target") == AC_TARGET)]
    result["equipment_effects"] = kept + _ac_entries(explanation, names_by_id)
    return Projection(result, True, "", armor_class=explanation["effective"], previous_armor_class=previous,
                      explanation=explanation, gaps=world.gaps, notes=world.notes, status=projected_status)
