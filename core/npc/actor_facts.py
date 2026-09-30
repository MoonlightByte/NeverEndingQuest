"""Small owner-labelled sheet facts for companion advice, not action authority."""

from collections.abc import Mapping
import json


def actor_sheet_facts(name, sheet, status=None):
    """Preserve ownership and unknowns; never infer an ally's gear from the NPC."""
    if not isinstance(sheet, Mapping):
        return f"{name}: sheet unavailable; equipment and abilities unknown."
    items = []
    equipment = sheet.get("equipment")
    if isinstance(equipment, list):
        for item in equipment:
            if not isinstance(item, Mapping):
                continue
            label = item.get("item_name") or item.get("name")
            if not label:
                continue
            items.append({key: item[key] for key in (
                "item_name", "name", "quantity", "equipped", "charges",
            ) if key in item})
    facts = {"owner": name, "status": status or "see current HP/conditions",
             "hp": sheet.get("hitPoints"), "conditions": sheet.get("condition_affected", []),
             "equipment": items if isinstance(equipment, list) else "unknown"}
    for key in ("attacksAndSpellcasting", "classFeatures", "spellcasting"):
        value = sheet.get(key)
        # Spell slots/feature charges remain attached to the owning actor.
        if isinstance(value, (list, dict)):
            facts[key] = value
    return json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
