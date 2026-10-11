"""One-time repair of legacy sheets that used equipped to mean carried ready.

The engine has always enforced two hand slots. Older sheets sometimes marked
every weapon equipped. Retain one shield first, then weapons in saved order;
stow the excess without changing ownership, quantity, or item metadata.
"""
from typing import Any, Dict, List

VERSION = "two-hand-loadout-v1"
RECEIPT_FIELD = "nqlEquipmentMigration"


def migrate(sheet: Dict[str, Any]) -> List[str]:
    """Mutate only impossible, un-migrated loadouts; return recorded repairs.

    This is called at character load or on a fresh generated NPC draft before
    its first save, never to excuse a newly proposed illegal equip action.
    An existing receipt prevents repeated automatic choices.
    """
    if sheet.get(RECEIPT_FIELD):
        return []
    equipment = sheet.get("equipment")
    if not isinstance(equipment, list):
        return []
    held = [i for i, item in enumerate(equipment)
            if isinstance(item, dict) and item.get("equipped") is True
            and item.get("quantity", 1) == 1
            and (item.get("item_type") == "weapon"
                 or (item.get("item_type") == "armor"
                     and item.get("armor_category") == "shield"))]
    if len(held) <= 2:
        return []
    shields = [i for i in held if equipment[i].get("armor_category") == "shield"]
    weapons = [i for i in held if i not in shields]
    kept = shields[:1] + weapons[:2 - bool(shields)]
    stowed = []
    for i in held:
        if i in kept:
            continue
        item = equipment[i]
        stowed.append({"index": i, "item_name": item.get("item_name", ""),
                       "nql_id": item.get("nql_id"), "previous_equipped": True})
        item["equipped"] = False
    sheet[RECEIPT_FIELD] = {"version": VERSION, "kept_indices": kept, "stowed": stowed}
    return [f"equipment[{item['index']}].equipped=legacy_stowed" for item in stowed]
