# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""#145: one item handed between party members in an agentic fight.

An actor's intent may carry ``handOver`` {item: {nqlId|catalog_id}, toId,
quantity}: the actor gives from its own sheet to another present party member
whose sheet is a character file, once per turn, after its Bonus Action and
before its Action. ``core.nql.transfer.transact`` moves the item in one engine
request at staging, the only engine call. The event keeps both owners' whole
``equipment`` lists (or ``ammunition`` lists, #902) from just before and just
after it, so a replay sets them and never calls the engine again.
"""
from copy import deepcopy

HAND_OVER_KEYS = frozenset({"item", "toId", "quantity"})


class HandOverRefused(ValueError):
    """A hand-over that cannot be staged as given. ``refusal`` is the typed
    #968 record when the player's own stock is short, else None."""

    def __init__(self, reason, refusal=None):
        super().__init__(reason)
        self.refusal = refusal


def _receiver(encounter, actor, hand_over, durable_owners):
    from core.managers.combat_state import combatant_by_id, is_party_member, normalize_status
    receiver = combatant_by_id(encounter, hand_over.get("toId"))
    if receiver is not None and receiver.get("combatantId") == actor.get("combatantId"):
        raise HandOverRefused("handOver.toId names the giver; a hand-over goes to another party member")
    if (receiver is None or receiver.get("type") not in ("player", "npc") or not is_party_member(receiver)
            or normalize_status(receiver.get("status")) not in ("alive", "unconscious")
            or receiver.get("name") not in durable_owners):
        raise HandOverRefused(
            "handOver.toId must name another present party member with a character sheet "
            "(the player or a party NPC), never an enemy")
    return receiver


def stage_hand_over(encounter, characters, actor, hand_over, event_id, durable_owners, player=False):
    """Move the item through the engine on the staged sheets.

    Returns (record, characters): the event's ``handOver`` record and new
    sheets where only the two owners' moved field changed. Raises
    HandOverRefused with the reason, nothing changed.
    """
    from core.nql import ammunition, genesis, item_use, transfer
    if not isinstance(hand_over, dict) or not set(hand_over) <= HAND_OVER_KEYS:
        raise HandOverRefused("handOver must be one object {item, toId, quantity}; one hand-over per turn")
    quantity = hand_over.get("quantity", 1)
    if type(quantity) is not int or quantity < 1:
        raise HandOverRefused("handOver.quantity must be a whole number of at least 1")
    giver_name = actor.get("name")
    if giver_name not in durable_owners or actor.get("type") not in ("player", "npc"):
        raise HandOverRefused("only a party member with a character sheet hands over an item")
    receiver = _receiver(encounter, actor, hand_over, durable_owners)
    giver = characters.get(giver_name)
    taker = characters.get(receiver["name"])
    if not isinstance(giver, dict) or not isinstance(taker, dict):
        raise HandOverRefused("handOver needs both party members' sheets")
    found = item_use.resolve_row(giver, hand_over.get("item"))
    if found is None:
        raise HandOverRefused(
            "handOver.item must name one row of the giver's own equipment by nqlId or catalog_id, never a name")
    row = found[1]
    name = row.get("item_name")
    same_name = [r for r in giver.get("equipment") or []
                 if isinstance(r, dict) and str(r.get("item_name", "")).strip().lower() == str(name).strip().lower()]
    if len(same_name) != 1:
        # The engine moves the giver's row by name (core/nql/transfer.py).
        raise HandOverRefused("%s's sheet lists more than one %r row; the hand-over cannot tell which one moves"
                              % (giver_name, name))
    if row.get("equipped") is True and row.get("item_type") == "armor":
        raise HandOverRefused("%s is worn armor: it cannot be handed over during a fight" % name)
    declared = ammunition.declared_row(giver, name)
    field = "ammunition" if declared is not None else "equipment"
    stock = (declared[1] if declared else row).get("quantity")
    stock = stock if type(stock) is int else 1
    if quantity > stock:
        refusal = None
        if player:
            refusal = {"owner": giver_name, "kind": "item", "name": name, "item": deepcopy(hand_over.get("item")),
                       "before": stock, "need": quantity, "max": None, "actor": giver_name}
        raise HandOverRefused("only %d %r on %s's sheet, handOver asked for %d" % (stock, name, giver_name, quantity),
                              refusal)
    outcome = transfer.transact(giver, taker, name, quantity, location="party",
                                request_id="combat-handover:%s" % event_id,
                                reserved=genesis.held_ids_on_disk())
    if not outcome.ok:
        raise HandOverRefused("the engine refused the hand-over: %s" % outcome.reason)
    staged = dict(characters)
    rows = []
    for owner, sheet, moved in ((giver_name, giver, outcome.giver), (receiver["name"], taker, outcome.receiver)):
        entry = {"owner": owner, "before": deepcopy(sheet.get(field) or []), "after": deepcopy(moved.get(field) or [])}
        rows.append(entry)
        staged[owner] = deepcopy(sheet)
        staged[owner][field] = deepcopy(entry["after"])
    record = {"item": deepcopy(hand_over["item"]), "fromId": actor.get("combatantId"),
              "toId": receiver.get("combatantId"), "fromName": giver_name, "toName": receiver["name"],
              "itemName": outcome.item_name, "quantity": outcome.quantity, "receipt": deepcopy(outcome.receipt),
              "field": field, "rows": rows}
    return record, staged


def apply_hand_over(characters, record):
    """Replay: set each owner's moved field to its journaled list. Never the engine."""
    for entry in record.get("rows") or []:
        sheet = characters.get(entry.get("owner"))
        if not isinstance(sheet, dict):
            raise ValueError("Hand-over owner is not durably addressable: %r" % entry.get("owner"))
        sheet[record["field"]] = deepcopy(entry["after"])


def hand_over_problems(record):
    """validate_event's check of an event's ``handOver`` record."""
    if not isinstance(record, dict):
        return ["handOver must be an object"]
    problems = []
    if not isinstance(record.get("item"), dict):
        problems.append("handOver item must be a typed reference")
    for key in ("fromId", "toId", "fromName", "toName", "itemName"):
        if not isinstance(record.get(key), str) or not record.get(key):
            problems.append("handOver %s must be a nonempty string" % key)
    if type(record.get("quantity")) is not int or record.get("quantity") < 1:
        problems.append("handOver quantity must be a positive integer")
    if record.get("field") not in ("equipment", "ammunition"):
        problems.append("handOver field must be equipment or ammunition")
    rows = record.get("rows")
    if not isinstance(rows, list) or len(rows) != 2:
        return problems + ["handOver rows must hold exactly the giver and the receiver"]
    owners = []
    for entry in rows:
        if not isinstance(entry, dict) or not isinstance(entry.get("owner"), str) or not entry.get("owner"):
            problems.append("handOver row needs an owner name")
            continue
        owners.append(entry["owner"])
        for key in ("before", "after"):
            value = entry.get(key)
            if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
                problems.append("handOver %s list of %s must hold objects" % (key, entry["owner"]))
    if owners != [record.get("fromName"), record.get("toName")] or len(set(owners)) != 2:
        problems.append("handOver rows must be the giver's, then the receiver's")
    return problems
