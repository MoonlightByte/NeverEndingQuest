# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""T109: resolve natural-language inventory references against real state.

One accepted DM response can name people, items, and containers in prose
("Kira, take the insignia out of the locker"). This callsite hands the model
the REAL roster, the REAL resource rows, and the REAL containers, and asks it
to name the exact rows those phrases point at.

This is STAGE 1 of the canonical workflow: the mapper. It emits ``movements``
-- structured, atomic, both-ended -- which utils/inventory_resolution.py turns
into SLICES. Code downstream consumes slices and nothing else; it never sees
the command text.

Scope boundaries (owner-ratified):
  * The model resolves references, classifies intent, and maps movements. It
    never calculates, never invents a person, item, container, quantity, or
    charge, and never writes state.
  * Every movement it emits carries BOTH a source and a destination. A
    one-ended movement is what commits a one-sided loss, so code refuses one
    rather than completing it by inference.
  * Code owns arithmetic, identity, conservation, ordering, and atomicity.
    Quantities and charges are re-derived from the snapshot by
    utils/inventory_resolution.py; a phrase such as "my wand of 99 magic
    missiles" resolves to the ONE wand actually owned and the conflict is
    recorded, never multiplied.
  * A refusal is only legitimate when the person, item, or container truly is
    not in state. That refusal arrives as ``blocking_problem`` for the narrator
    to voice in fiction; it is never surfaced as a system error.

Failure handling: this module raises InventoryResolutionError carrying a
``correction`` string. The caller owns the retry ceiling and may pass that
string back through ``correction`` for one bounded self-heal attempt, exactly
as the T108 classifier does.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional

import config
import model_config
from core.ai import api_client
from utils.character_sheet_contract import extract_json_object
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.inventory_resolution import (
    resolution_facts,
    resolution_shape_errors,
    resolution_state_errors,
    index_snapshot,
    snapshot_shape_errors,
)


register_callsite("T109", "core/ai/inventory_resolver.py", 176)

_SYSTEM_PROMPT = """You resolve natural-language references in an accepted
role-playing action against the supplied game state. You do not narrate,
decide outcomes, move anything, or calculate.

You receive the party roster and who is present, each character's resource
rows (equipment, ammunition, currency with quantities and charges), the
accessible containers with their ids, locations, and contents, the current
location, the speaker, and the accepted action prose.

Return JSON only with exactly:
{"actor":{"resolved":"exact party member name or null","confidence":"high|low"},
 "resources":[{"reference":"phrase as written",
   "resolved_name":"exact name from state or null",
   "family":"equipment|ammunition|currency|null",
   "owner":"exact holder name or container id or null",
   "available_quantity":integer from state or null,
   "found":true|false,
   "discrepancy":"note if phrasing conflicts with state, else null"}],
 "movements":[{"reference":"phrase as written",
   "kind":"give|store|retrieve|purchase|sell|consume|discard",
   "source":{"kind":"character|container|external","id":"exact name, container id, or null"},
   "destination":{"kind":"character|container|external","id":"exact name, container id, or null"},
   "family":"equipment|ammunition|currency",
   "resolved_name":"exact name from state",
   "stated_quantity":integer the wording asserts, or null}],
 "intent":"store|retrieve|give|consume|purchase|sell|view|attack|other",
 "blocking_problem":"short player-facing reason nothing can proceed, or null"}

Rules for movements:
movements is the structured list of things that actually change hands. Add one
entry for every resource the action moves, and none for anything it merely
mentions. When nothing moves, movements is an empty array.
Every movement carries BOTH a source and a destination. A movement with only
one end is never acceptable: if a thing leaves someone, name where it goes; if
it arrives, name where it came from. When the counterpart truly is outside the
party and the containers, use kind external for that ONE end only; never for
both ends. External is allowed only here: a purchase, where the goods arrive
from external and the coin leaves toward external; a sale, where the goods
leave toward external and the coin arrives from external; and something used
up or thrown away, which leaves toward external.
A trade has two movements, one for the goods and one for the coin, and both
are listed. Giving, storing, and retrieving never use external: those move
between two tracked places and both must be named.
source.id and destination.id are exact character names from the roster or
exact container ids from the supplied containers. Never a description, never a
role word, never a merchant's name for a tracked holder.
The source is where the thing IS right now according to state, not where the
sentence puts it. resolved_name is that exact state row name.
stated_quantity is only what the wording asserts, copied as a number. When the
wording gives no number, use null. Never take stated_quantity from state, and
never adjust it to match state; the conflict is reported elsewhere.
A person can move something they hold to another person even when they are the
one speaking: source is the current holder, destination is the receiver, and
both are named even when they are the actor.

Rules:
resources lists the items, ammunition, and currency the action needs, one entry
per phrase, with reference copied as written. People are never resources; the
person acting belongs in actor.
A container named as the source or destination gets its own entry: family null,
owner set to its exact container id, resolved_name set to its exact state name,
available_quantity null, found true when that container is supplied.
Quantities and charges come ONLY from the supplied state. Never take a number
from the phrasing. Phrasing that contradicts state still resolves to the real
row: record the real row and put the conflict in discrepancy. Example: a
reference to a wand of 99 charges resolves to the one wand actually held with
its real charges, with the conflict noted.
Players speak loosely. Partial names, nicknames, plurals, and generic words
such as the locker, the chest, my bow, or some coins are normal. Resolve such
wording to the state entity it denotes and note the wording difference in
discrepancy. Loose wording is never by itself a reason to report found false.
Entities are named by the role the sentence gives them, not by exact wording.
When the action stores into or retrieves from a container and exactly one
supplied accessible container can fill that role, that container is the one
meant, whatever word the player used for it. A different kind-word for the same
object, such as strongbox, footlocker, or safe for a supplied chest, is a
wording difference to note in discrepancy, never a missing container. Report a
container as not found only when no supplied container can fill the role.
owner is the exact character name or container id from state that holds the row
right now, even when the phrasing implies a different holder.
Only when no supplied row, character, or container can be the thing named, set
found to false with resolved_name, owner, family, and available_quantity null,
and write a short in-fiction blocking_problem the narrator can voice. Leave
blocking_problem null whenever the action can proceed.
actor is the party member who physically performs the action, which may differ
from the speaker; use null with confidence low when it cannot be determined
from the supplied roster, and give a blocking_problem naming that difficulty.
Never invent items, characters, containers, quantities, or charges. Never add,
subtract, convert, or total anything. Use exact spellings from state."""


class InventoryResolutionError(ValueError):
    """T109 could not produce a state-backed resolution.

    ``correction`` is the exact text a bounded retry may hand back to the
    model so it re-resolves against the real rows.
    """

    def __init__(self, message: str, *, correction: Optional[str] = None) -> None:
        super().__init__(message)
        self.correction = correction or message


def _provider_config(provider: str) -> Dict[str, Any]:
    """Select the config dict for one already-pinned provider snapshot."""
    if provider == "openai":
        return config.INVENTORY_RESOLVE_T109_TERRA
    if provider == "gemini":
        return config.INVENTORY_RESOLVE_T109_GEMINI_PRO_LOW
    if provider == "lmstudio":
        return config.INVENTORY_RESOLVE_T109_LMSTUDIO
    return config.INVENTORY_RESOLVE_T109_LEGACY


def _reject_duplicate_keys(pairs):
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("T109 response contained a duplicate JSON key")
        value[key] = item
    return value


def _contract_view(value: Mapping[str, Any]) -> Dict[str, Any]:
    """Rebuild the validated contract so callers get exact, stable types."""
    actor = value["actor"]
    resources: List[Dict[str, Any]] = []
    for resource in value["resources"]:
        resources.append(
            {
                "reference": resource["reference"],
                "resolved_name": resource["resolved_name"],
                "family": resource["family"],
                "owner": resource["owner"],
                "available_quantity": resource["available_quantity"],
                "found": resource["found"],
                "discrepancy": resource["discrepancy"],
            }
        )
    movements: List[Dict[str, Any]] = []
    for movement in value["movements"]:
        movements.append(
            {
                "reference": movement["reference"],
                "kind": movement["kind"],
                "source": {
                    "kind": movement["source"]["kind"],
                    "id": movement["source"]["id"],
                },
                "destination": {
                    "kind": movement["destination"]["kind"],
                    "id": movement["destination"]["id"],
                },
                "family": movement["family"],
                "resolved_name": movement["resolved_name"],
                "stated_quantity": movement["stated_quantity"],
            }
        )
    return {
        "actor": {
            "resolved": actor["resolved"],
            "confidence": actor["confidence"],
        },
        "resources": resources,
        "movements": movements,
        "intent": value["intent"],
        "blocking_problem": value["blocking_problem"],
    }


def resolve_inventory_references(
    snapshot: Mapping[str, Any],
    *,
    correction: Optional[str] = None,
) -> Dict[str, Any]:
    """Make one resolve-only call against the supplied real-state snapshot.

    ``snapshot`` must come from
    utils.inventory_resolution.build_resolution_snapshot, which projects real
    character sheets and real containers. The caller owns the retry ceiling.
    """
    shape_errors = snapshot_shape_errors(snapshot)
    if shape_errors:
        raise InventoryResolutionError(
            "T109 received an unusable state snapshot: " + "; ".join(shape_errors)
        )
    payload: Dict[str, Any] = {"resolution_request": dict(snapshot)}
    if correction:
        payload["previous_validation_error"] = str(correction)[:1000]
    # Snapshot the provider ONCE: the config dict and the transport must
    # describe the same provider even if the UI switches mid-turn.
    provider = model_config.get_provider()
    provider_config = _provider_config(provider)
    options = {
        key: value for key, value in provider_config.items() if key != "model"
    }
    response = capture_and_fanout(
        "T109",
        api_client.create_completion,
        _request_provider=provider,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            },
        ],
        model=provider_config["model"],
        **options,
    )
    content = response.choices[0].message.content
    if not isinstance(content, str) or not content.strip():
        raise InventoryResolutionError("T109 returned an empty response")
    # Local/Custom providers force response_format off, so replies can arrive
    # fenced or prose-wrapped. Extract before parsing.
    blob = extract_json_object(content)
    if blob is None:
        raise InventoryResolutionError(
            "T109 response contained no complete JSON object"
        )
    try:
        value = json.loads(blob, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        raise InventoryResolutionError(f"T109 response was not valid JSON: {exc}")
    errors = resolution_shape_errors(value)
    if errors:
        raise InventoryResolutionError(
            "T109 response violated the resolution contract: " + "; ".join(errors),
            correction="Your previous reply violated the output contract: "
            + "; ".join(errors),
        )
    state_errors = resolution_state_errors(snapshot, value)
    if state_errors:
        raise InventoryResolutionError(
            "T109 response did not match supplied state: " + "; ".join(state_errors),
            correction="Your previous reply did not match the supplied state: "
            + "; ".join(state_errors)
            + ". Re-resolve using only the rows in the state packet.",
        )
    return _contract_view(value)


def resolve_inventory_facts(
    snapshot: Mapping[str, Any],
    *,
    correction: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve, then derive the deterministic facts code acts on.

    Returns {"resolution": <verbatim validated contract>, "facts": <derived>}.
    Every quantity and charge in ``facts`` is re-read from ``snapshot``; the
    model's echoed numbers are reported alongside for conflict detection but
    are never authoritative.
    """
    resolution = resolve_inventory_references(snapshot, correction=correction)
    lookup = index_snapshot(snapshot)
    return {
        "resolution": resolution,
        "facts": resolution_facts(snapshot, resolution, index=lookup),
    }
