"""Typed healing consumables: the engine spends, rolls and caps the heal (#1331)."""
from copy import deepcopy
import uuid

from core.nql import apply, checks, genesis, item_catalog


def resolve_row(sheet, reference):
    """Resolve exactly one equipment row by its stored id, never its name."""
    if not isinstance(reference, dict) or len(reference) != 1:
        return None
    if set(reference) == {"nqlId"}:
        field, value = "nql_id", reference["nqlId"]
    elif set(reference) == {"catalog_id"}:
        field, value = "catalog_id", reference["catalog_id"]
    else:
        return None
    if not isinstance(value, str) or not value:
        return None
    rows = [(i, r) for i, r in enumerate((sheet or {}).get("equipment") or [])
            if isinstance(r, dict) and r.get(field) == value]
    return rows[0] if len(rows) == 1 else None


def use_data(row):
    entry = item_catalog.entry(row.get("catalog_id")) or {}
    use = entry.get("use")
    return use if isinstance(use, dict) and use.get("activation") == "bonus_action" else None


def available(sheet):
    result = []
    for row in (sheet or {}).get("equipment") or []:
        if (isinstance(row, dict) and type(row.get("quantity")) is int
                and row["quantity"] > 0 and use_data(row)):
            ref = {"nqlId": row["nql_id"]} if row.get("nql_id") else {"catalog_id": row.get("catalog_id")}
            if resolve_row(sheet, ref):
                result.append({"item": ref, "name": row.get("item_name"), "use": use_data(row)})
    return result


def heal(owner, target, reference, *, seed=None):
    """Return engine HP, quantity and roll receipt; never mutate the input sheets."""
    found = resolve_row(owner, reference)
    if found is None:
        raise ValueError("potion item id does not resolve to one owned row")
    index, row = found
    use = use_data(row)
    if use is None:
        raise ValueError("item has no typed bonus-action use")
    count = use["heal"]["count"]
    sides = use["heal"]["sides"]
    bonus = use["heal"]["bonus"]
    if any(type(value) is not int for value in (count, sides, bonus)):
        raise ValueError("healing count, sides and bonus must be typed integers")
    sheets = [deepcopy(owner)] if owner["name"] == target["name"] else [deepcopy(owner), deepcopy(target)]
    cid, tid = genesis.character_id(owner), genesis.character_id(target)
    iid = row.get("nql_id") or "item:consumable"
    q = genesis._q
    seed = seed or checks.fresh_seed()
    source = 'rules { transfer unequips; wear any; }\nclock "second" at 0;\nlocation "loc:combat" named "Combat";\n'
    for sheet in sheets:
        source += (f'character {q(genesis.character_id(sheet))} named {q(sheet["name"])} at "loc:combat" {{ '
                   f'resource "hp" = {sheet["hitPoints"]} min 0 max {sheet["maxHitPoints"]}; }}\n')
    source += (f'item {q(iid)} named {q(row["item_name"])} {{ owner {q(cid)}; custody character {q(cid)}; '
               f'quantity {row["quantity"]}; }}\n')
    source += 'equipment "nql-equipment-v1" { slot "hand" capacity 2; }\n'
    if cid != tid:
        source += f'relation character {q(tid)} "party-member" character {q(cid)} = 1;\n'
    source += f'''battle "nql-battle-v1" {{
 health "hp"; defense "defense"; initiative "initiative";
 party {q(cid)} relation "party-member" strength 1;
 roll sides 20 miss 1 critical 20 multiply 2;
 grid "feet" square 5; clock "second" round 6;
 seed {int(seed[0])} {int(seed[1])}; zero protected stable_down opposition dead;
 action "ability:consumable-heal";
}}
ability "ability:consumable-heal" named "Consumable healing" {{
 parameter "actor" character; parameter "target" character;
 action actor param "actor" phase exploration;
 roll heal param "target" resource "hp" dice {count} sides {sides} bonus from param "target" {{ constant {bonus}; }};
}}
'''
    response = apply.call({"world": source, "world_name": "consumable-heal.nql",
        "actions": f'consume {q(iid)} from {q(cid)} by 1;\n'
                   f'invoke "ability:consumable-heal" {{ "actor" = character {q(cid)}; "target" = character {q(tid)}; roll 0 engine; }};',
        "actor": {"kind": "character", "id": cid}, "request": "consumable:" + uuid.uuid4().hex,
        "status": [tid], "items_at": [{"kind": "character", "id": cid}]})
    if not response.get("ok"):
        raise ValueError("potion engine refused: %s" % (response.get("diagnostics") or response.get("fault") or response.get("error")))
    hp = next(s["resources"]["hp"]["current"] for s in response["status"] if s["character"]["id"] == tid)
    items = next(v["items"] for v in response["items_at"] if v["at"]["id"] == cid)
    quantity = next((i["quantity"] for i in items if i["id"] == iid), 0)
    rolls = [e["resource_roll"] for e in response["receipt"]["events"] if "resource_roll" in e]
    return {"hitPoints": hp, "quantity": quantity, "rolls": rolls}
