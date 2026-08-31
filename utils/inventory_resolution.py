# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""SLICES: the single interchange format between the mapper and code.

This module is PURE: no file I/O, no network, no model calls, no global
mutable state, no clock. Every function is a total function of its arguments
and may be exercised directly.

The canonical workflow (owner-ratified) runs through here:

  1. AGENT MAPS -- ``core/ai/inventory_resolver.py`` reads the natural language
     against the REAL state and emits structured movements. It never
     calculates and never invents.
  2. CODE PROCESSES SLICES ONLY -- ``derive_slices`` turns those movements into
     slices: atomic, fully structured, no prose inside except a verbatim
     provenance phrase code never interprets. Anything that cannot be pinned to
     state comes back in ``unresolved`` with a machine reason, never a guess.
  4. CODE SELF-VALIDATES -- ``slice_contract_errors`` gates every slice:
     endpoint existence, both endpoints present and distinct, family and
     identity present, row identity matching the source row, quantity read
     from state, dependency ordering. Slices this module derived pass the
     IDENTICAL gate; there is no privileged path.

Three hard rules are enforced here:
  1. Items never permute. Quantities and charges always come from the state
     row, never from the model's echo of them. When the phrased number
     disagrees with state, the state number wins, the identity is reported by
     ``permuted_slice_identities``, and the phrased number contributes nothing.
  2. No prose parsing. Matching is exact normalized equality between a
     model-supplied identifier and a state-supplied identifier. There is no
     regex, keyword list, verb list, or substring test over player or model
     prose anywhere in this module or in the seams that consume it.
  3. No claim is not permission. ``facts_for`` returning None means the
     resolution was unavailable, and every consumer must refuse rather than
     commit -- see ``movement_claim_fault`` and
     ``unverified_movement_refusal``.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from utils.inventory_integrity import normalize_inventory_name


FAMILIES: Tuple[str, ...] = ("equipment", "ammunition", "currency")
INTENTS: Tuple[str, ...] = (
    "store",
    "retrieve",
    "give",
    "consume",
    "purchase",
    "sell",
    "view",
    "attack",
    "other",
)
CONFIDENCE_LEVELS: Tuple[str, ...] = ("high", "low")
_CURRENCY_ORDER: Tuple[str, ...] = ("gold", "silver", "copper")

# ---------------------------------------------------------------------------
# SLICE contract
#
# A SLICE is the ONLY interchange format between the mapper (the model that
# reads prose against real state) and code. It is an atomic, fully structured
# movement with no prose left inside it except the verbatim provenance phrase,
# which code never inspects for meaning.
#
#   {slice_id, kind, actor, source{kind,id}, destination{kind,id}, family,
#    canonical_name, row_identity, quantity, stated_quantity, provenance}
#
# Every endpoint is a state identity. Every quantity is read from state. A
# movement whose endpoints or row cannot be verified against state never
# becomes a slice: it becomes an ``unresolved`` entry carrying the reason.
# ---------------------------------------------------------------------------
SLICE_KINDS: Tuple[str, ...] = (
    "give",
    "store",
    "retrieve",
    "purchase",
    "sell",
    "consume",
    "discard",
)
ENDPOINT_KINDS: Tuple[str, ...] = ("character", "container", "external")
# An endpoint outside the tracked world is only legitimate where the fiction
# genuinely has no tracked counterpart. A trade has two legs and each has one
# untracked end: goods arrive from the vendor while coin leaves toward them
# (purchase), or goods leave toward the vendor while coin arrives (sale).
# Consuming or discarding sends the row nowhere tracked. Both ends untracked
# is never a movement this system owns.
_EXTERNAL_SOURCE_KINDS: Tuple[str, ...] = ("purchase", "sell")
_EXTERNAL_DESTINATION_KINDS: Tuple[str, ...] = (
    "purchase",
    "sell",
    "consume",
    "discard",
)
SLICE_BOTH_ENDPOINTS_EXTERNAL = "slice_has_no_tracked_endpoint"

# Reasons a movement could not become a slice. These are code-derived and are
# safe to show to the mapper as a correction.
SLICE_KIND_INVALID = "slice_kind_invalid"
SLICE_FAMILY_INVALID = "slice_family_invalid"
SLICE_NAME_MISSING = "slice_canonical_name_missing"
SLICE_ENDPOINT_MALFORMED = "slice_endpoint_malformed"
SLICE_ENDPOINT_KIND_INVALID = "slice_endpoint_kind_invalid"
SLICE_ENDPOINT_NOT_IN_STATE = "slice_endpoint_not_in_state"
SLICE_ENDPOINT_EXTERNAL_NOT_ALLOWED = "slice_external_endpoint_not_allowed"
SLICE_ENDPOINTS_IDENTICAL = "slice_source_and_destination_identical"
SLICE_CONTAINER_NOT_ACCESSIBLE = "slice_container_not_accessible"
SLICE_ROW_NOT_AT_SOURCE = "slice_row_not_at_source"
SLICE_ROW_AMBIGUOUS = "slice_row_ambiguous_at_source"
SLICE_QUANTITY_UNREADABLE = "slice_state_quantity_unreadable"
SLICE_STATED_QUANTITY_INVALID = "slice_stated_quantity_invalid"
SLICE_STATED_EXCEEDS_STATE = "slice_stated_quantity_exceeds_state"
SLICE_DEPENDENCY_ORDER = "slice_consumes_before_it_is_produced"
SLICE_DUPLICATE_ID = "slice_id_is_not_unique"

# Deterministic discrepancy codes. These are code-derived; the model's own
# free-text ``discrepancy`` note is carried separately as ``model_discrepancy``.
CODE_MODEL_QUANTITY_DISAGREES = "quantity_disagrees_with_state"
CODE_UNKNOWN_OWNER = "owner_not_in_state"
CODE_OWNER_MISMATCH = "owner_differs_from_state"
CODE_AMBIGUOUS_OWNER = "owner_ambiguous_in_state"
CODE_ROW_ABSENT = "row_absent_from_state"
CODE_ROW_PRESENT = "row_present_but_reported_absent"
CODE_FAMILY_MISSING = "family_missing"
CODE_NAME_MISSING = "resolved_name_missing"
CODE_MALFORMED_STATE_QUANTITY = "state_quantity_unreadable"
CODE_CONTAINER_NOT_ACCESSIBLE = "container_not_accessible"
CODE_ACTOR_NOT_IN_PARTY = "actor_not_in_party"
CODE_ACTOR_NOT_PRESENT = "actor_not_present"
CODE_ACTOR_UNRESOLVED = "actor_unresolved"
CODE_ACTOR_LOW_CONFIDENCE = "actor_low_confidence"


# ---------------------------------------------------------------------------
# Small total helpers
# ---------------------------------------------------------------------------


def clean_text(value: Any) -> str:
    """Collapse whitespace for display; never used for identity matching."""
    return " ".join(str(value if value is not None else "").split())


def normalize_identifier(value: Any) -> str:
    """Shared case/whitespace-insensitive identity used across inventory code."""
    return normalize_inventory_name(value)


def strict_quantity(value: Any) -> Optional[int]:
    """Return a nonnegative int, or None when the state value is unreadable."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def charges_of(value: Any) -> Optional[Dict[str, Optional[int]]]:
    """Return {current, max} charges from a state row, or None when absent."""
    if not isinstance(value, Mapping):
        return None
    current = strict_quantity(value.get("current"))
    maximum = strict_quantity(value.get("max"))
    if current is None and maximum is None:
        return None
    return {"current": current, "max": maximum}


# ---------------------------------------------------------------------------
# Snapshot construction (state -> model packet)
# ---------------------------------------------------------------------------


def _equipment_rows(rows: Any) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows if isinstance(rows, Sequence) and not isinstance(rows, str) else []:
        if not isinstance(row, Mapping):
            continue
        name = clean_text(row.get("item_name") or row.get("name"))
        if not name:
            continue
        entry: Dict[str, Any] = {
            "name": name,
            "quantity": strict_quantity(row.get("quantity")),
        }
        charges = charges_of(row.get("charges"))
        if charges is not None:
            entry["charges"] = charges
        if row.get("equipped") is True:
            entry["equipped"] = True
        if row.get("magical") is True:
            entry["magical"] = True
        result.append(entry)
    return result


def _ammunition_rows(rows: Any) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in rows if isinstance(rows, Sequence) and not isinstance(rows, str) else []:
        if not isinstance(row, Mapping):
            continue
        name = clean_text(row.get("name") or row.get("item_name"))
        if not name:
            continue
        result.append(
            {"name": name, "quantity": strict_quantity(row.get("quantity"))}
        )
    return result


def _currency_rows(currency: Any) -> List[Dict[str, Any]]:
    if not isinstance(currency, Mapping):
        return []
    ordered = [key for key in _CURRENCY_ORDER if key in currency]
    ordered.extend(
        sorted(str(key) for key in currency if str(key) not in _CURRENCY_ORDER)
    )
    rows: List[Dict[str, Any]] = []
    for key in ordered:
        rows.append(
            {"name": str(key), "quantity": strict_quantity(currency.get(key))}
        )
    return rows


def character_resource_rows(sheet: Mapping[str, Any]) -> Dict[str, Any]:
    """Project a real character sheet onto the resource rows T109 receives."""
    if not isinstance(sheet, Mapping):
        return {"name": "", "equipment": [], "ammunition": [], "currency": []}
    return {
        "name": clean_text(sheet.get("name")),
        "equipment": _equipment_rows(sheet.get("equipment")),
        "ammunition": _ammunition_rows(sheet.get("ammunition")),
        "currency": _currency_rows(sheet.get("currency")),
    }


def container_resource_rows(container: Mapping[str, Any]) -> Dict[str, Any]:
    """Project a real storage container onto the rows T109 receives."""
    if not isinstance(container, Mapping):
        return {
            "id": "",
            "name": "",
            "type": "",
            "location_id": "",
            "location_name": "",
            "equipment": [],
            "ammunition": [],
            "currency": [],
        }
    return {
        "id": clean_text(container.get("id")),
        "name": clean_text(container.get("deviceName") or container.get("name")),
        "type": clean_text(container.get("deviceType") or container.get("type")),
        "location_id": clean_text(
            container.get("locationId") or container.get("location_id")
        ),
        "location_name": clean_text(
            container.get("locationName") or container.get("location_name")
        ),
        "equipment": _equipment_rows(
            container.get("contents")
            if container.get("contents") is not None
            else container.get("equipment")
        ),
        "ammunition": _ammunition_rows(container.get("ammunition")),
        "currency": _currency_rows(container.get("currency")),
    }


def _party_entry(entry: Any) -> Optional[Dict[str, Any]]:
    if isinstance(entry, Mapping):
        name = clean_text(entry.get("name"))
        if not name:
            return None
        present = entry.get("present")
        return {"name": name, "present": True if present is None else bool(present)}
    name = clean_text(entry)
    if not name:
        return None
    return {"name": name, "present": True}


def build_resolution_snapshot(
    *,
    party: Sequence[Any],
    characters: Sequence[Mapping[str, Any]],
    containers: Sequence[Mapping[str, Any]],
    location: Any,
    speaker: Any,
    action: Any,
) -> Dict[str, Any]:
    """Build the exact state packet T109 resolves against.

    ``characters`` are real character sheets and ``containers`` are real
    storage records; this function only projects and normalizes them. Callers
    perform the file reads, so this module stays pure.
    """
    if isinstance(location, Mapping):
        location_view = {
            "id": clean_text(location.get("id") or location.get("locationId")),
            "name": clean_text(location.get("name") or location.get("locationName")),
        }
    else:
        location_view = {"id": "", "name": clean_text(location)}

    party_view: List[Dict[str, Any]] = []
    seen_party = set()
    for entry in party or []:
        member = _party_entry(entry)
        if member is None:
            continue
        key = normalize_identifier(member["name"])
        if key in seen_party:
            continue
        seen_party.add(key)
        party_view.append(member)

    character_view: List[Dict[str, Any]] = []
    for sheet in characters or []:
        projected = character_resource_rows(sheet)
        if projected["name"]:
            character_view.append(projected)

    container_view: List[Dict[str, Any]] = []
    for container in containers or []:
        projected = container_resource_rows(container)
        if not projected["id"]:
            continue
        projected["accessible"] = bool(
            location_view["id"]
            and normalize_identifier(projected["location_id"])
            == normalize_identifier(location_view["id"])
        )
        container_view.append(projected)

    return {
        "location": location_view,
        "speaker": clean_text(speaker),
        "action": clean_text(action),
        "party": party_view,
        "characters": character_view,
        "containers": container_view,
    }


def snapshot_shape_errors(snapshot: Any) -> List[str]:
    """Return reasons the snapshot cannot be resolved against, if any."""
    errors: List[str] = []
    if not isinstance(snapshot, Mapping):
        return ["snapshot must be a mapping"]
    for key in ("location", "speaker", "action", "party", "characters", "containers"):
        if key not in snapshot:
            errors.append(f"snapshot missing key: {key}")
    if not errors:
        if not isinstance(snapshot.get("party"), list):
            errors.append("snapshot party must be a list")
        if not isinstance(snapshot.get("characters"), list):
            errors.append("snapshot characters must be a list")
        if not isinstance(snapshot.get("containers"), list):
            errors.append("snapshot containers must be a list")
        if not clean_text(snapshot.get("action")):
            errors.append("snapshot action prose is empty")
    return errors


# ---------------------------------------------------------------------------
# Snapshot index (opaque, in-memory only)
# ---------------------------------------------------------------------------


def index_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Build an opaque lookup index over one snapshot.

    Keys are normalized identifiers. Lookup is exact normalized equality; no
    substring or fuzzy matching is performed anywhere in this module.
    """
    owners: Dict[str, Dict[str, Any]] = {}
    party: Dict[str, Dict[str, Any]] = {}
    rows: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    rows_by_name: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    container_names: Dict[str, List[str]] = {}

    for member in snapshot.get("party") or []:
        if not isinstance(member, Mapping):
            continue
        name = clean_text(member.get("name"))
        if not name:
            continue
        party[normalize_identifier(name)] = {
            "name": name,
            "present": bool(member.get("present", True)),
        }

    def _register(owner: Dict[str, Any], holder: Mapping[str, Any]) -> None:
        owners[normalize_identifier(owner["id"])] = owner
        for family in FAMILIES:
            for row in holder.get(family) or []:
                if not isinstance(row, Mapping):
                    continue
                name = clean_text(row.get("name"))
                if not name:
                    continue
                normalized = normalize_identifier(name)
                record = {
                    "owner": owner,
                    "family": family,
                    "name": name,
                    "normalized_name": normalized,
                    "quantity": strict_quantity(row.get("quantity")),
                    "charges": charges_of(row.get("charges")),
                }
                key = (owner["kind"], normalize_identifier(owner["id"]), family, normalized)
                existing = rows.get(key)
                if existing is None:
                    rows[key] = record
                    rows_by_name.setdefault((family, normalized), []).append(record)
                else:
                    # Duplicate display names inside one holder cannot be told
                    # apart by identity alone; mark both unusable rather than
                    # guess which row the reference meant.
                    existing["duplicate"] = True
                    record["duplicate"] = True
                    rows_by_name.setdefault((family, normalized), []).append(record)

    for character in snapshot.get("characters") or []:
        if not isinstance(character, Mapping):
            continue
        name = clean_text(character.get("name"))
        if not name:
            continue
        _register(
            {
                "kind": "character",
                "id": name,
                "name": name,
                "accessible": True,
                "present": party.get(normalize_identifier(name), {}).get(
                    "present", True
                ),
            },
            character,
        )

    for container in snapshot.get("containers") or []:
        if not isinstance(container, Mapping):
            continue
        container_id = clean_text(container.get("id"))
        if not container_id:
            continue
        display = clean_text(container.get("name"))
        owner = {
            "kind": "container",
            "id": container_id,
            "name": display or container_id,
            "accessible": bool(container.get("accessible", False)),
            "present": True,
            "location_id": clean_text(container.get("location_id")),
        }
        _register(owner, container)
        if display:
            container_names.setdefault(normalize_identifier(display), []).append(
                container_id
            )

    return {
        "owners": owners,
        "party": party,
        "rows": rows,
        "rows_by_name": rows_by_name,
        "container_names": container_names,
    }


def canonical_row_key(
    owner_kind: Optional[str],
    owner_id: Optional[str],
    family: Optional[str],
    resolved_name: Optional[str],
) -> Optional[str]:
    """Stable identity for one state row inside one snapshot.

    Identity is owner path + family + normalized name. Mutable amounts
    (quantity, charges) are deliberately excluded so the key does not change
    when the row is spent down.
    """
    if not owner_kind or not owner_id or not family or not resolved_name:
        return None
    return json.dumps(
        {
            "owner_kind": owner_kind,
            "owner_id": normalize_identifier(owner_id),
            "family": family,
            "name": normalize_identifier(resolved_name),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


# ---------------------------------------------------------------------------
# Contract validation (shape, then state)
# ---------------------------------------------------------------------------


_RESOLUTION_KEYS = {
    "actor",
    "resources",
    "movements",
    "intent",
    "blocking_problem",
}
_RESOURCE_KEYS = {
    "reference",
    "resolved_name",
    "family",
    "owner",
    "available_quantity",
    "found",
    "discrepancy",
}
_MOVEMENT_KEYS = {
    "reference",
    "kind",
    "source",
    "destination",
    "family",
    "resolved_name",
    "stated_quantity",
}
_ENDPOINT_KEYS = {"kind", "id"}


def _endpoint_shape_errors(value: Any, label: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(value, Mapping) or set(value) != _ENDPOINT_KEYS:
        return [f"{label} must be an object with exactly kind and id"]
    if value.get("kind") not in ENDPOINT_KINDS:
        errors.append(f"{label}.kind must be character, container, or external")
    if not _optional_text(value.get("id")):
        errors.append(f"{label}.id must be a string or null")
    return errors


def _optional_text(value: Any) -> bool:
    return value is None or isinstance(value, str)


def resolution_shape_errors(value: Any) -> List[str]:
    """Return contract violations in a raw T109 response, without state."""
    errors: List[str] = []
    if not isinstance(value, Mapping):
        return ["response is not a JSON object"]
    if set(value) != _RESOLUTION_KEYS:
        errors.append(
            "top-level keys must be exactly actor, resources, movements, "
            "intent, blocking_problem"
        )
        return errors
    actor = value.get("actor")
    if not isinstance(actor, Mapping) or set(actor) != {"resolved", "confidence"}:
        errors.append("actor must be an object with exactly resolved and confidence")
    else:
        if not _optional_text(actor.get("resolved")):
            errors.append("actor.resolved must be a string or null")
        if actor.get("confidence") not in CONFIDENCE_LEVELS:
            errors.append("actor.confidence must be high or low")
    if value.get("intent") not in INTENTS:
        errors.append("intent must be one of: " + ", ".join(INTENTS))
    if not _optional_text(value.get("blocking_problem")):
        errors.append("blocking_problem must be a string or null")
    resources = value.get("resources")
    if not isinstance(resources, list):
        errors.append("resources must be an array")
        return errors
    for position, resource in enumerate(resources):
        label = f"resources[{position}]"
        if not isinstance(resource, Mapping) or set(resource) != _RESOURCE_KEYS:
            errors.append(f"{label} must contain exactly the contract keys")
            continue
        if not isinstance(resource.get("reference"), str) or not resource[
            "reference"
        ].strip():
            errors.append(f"{label}.reference must be the phrase as written")
        if not _optional_text(resource.get("resolved_name")):
            errors.append(f"{label}.resolved_name must be a string or null")
        family = resource.get("family")
        if family is not None and family not in FAMILIES:
            errors.append(f"{label}.family must be equipment, ammunition, currency, or null")
        if not _optional_text(resource.get("owner")):
            errors.append(f"{label}.owner must be a string or null")
        quantity = resource.get("available_quantity")
        if quantity is not None and (
            isinstance(quantity, bool) or not isinstance(quantity, int)
        ):
            errors.append(f"{label}.available_quantity must be an integer or null")
        if not isinstance(resource.get("found"), bool):
            errors.append(f"{label}.found must be true or false")
        if not _optional_text(resource.get("discrepancy")):
            errors.append(f"{label}.discrepancy must be a string or null")

    movements = value.get("movements")
    if not isinstance(movements, list):
        errors.append("movements must be an array")
        return errors
    for position, movement in enumerate(movements):
        label = f"movements[{position}]"
        if not isinstance(movement, Mapping) or set(movement) != _MOVEMENT_KEYS:
            errors.append(f"{label} must contain exactly the contract keys")
            continue
        if not isinstance(movement.get("reference"), str) or not movement[
            "reference"
        ].strip():
            errors.append(f"{label}.reference must be the phrase as written")
        if movement.get("kind") not in SLICE_KINDS:
            errors.append(f"{label}.kind must be one of: " + ", ".join(SLICE_KINDS))
        if movement.get("family") not in FAMILIES:
            errors.append(
                f"{label}.family must be equipment, ammunition, or currency"
            )
        if not isinstance(movement.get("resolved_name"), str) or not movement[
            "resolved_name"
        ].strip():
            errors.append(f"{label}.resolved_name must be the exact state name")
        errors.extend(_endpoint_shape_errors(movement.get("source"), f"{label}.source"))
        errors.extend(
            _endpoint_shape_errors(movement.get("destination"), f"{label}.destination")
        )
        stated = movement.get("stated_quantity")
        if stated is not None and (
            isinstance(stated, bool) or not isinstance(stated, int) or stated <= 0
        ):
            errors.append(
                f"{label}.stated_quantity must be a positive integer or null"
            )
    return errors


def resolution_state_errors(
    snapshot: Mapping[str, Any],
    value: Mapping[str, Any],
    index: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Return violations that only the supplied state can reveal.

    These are correction-worthy: a bounded retry can hand them back to the
    model verbatim so it re-resolves against the real rows.
    """
    lookup = index if index is not None else index_snapshot(snapshot)
    errors: List[str] = []
    actor = value.get("actor") or {}
    resolved_actor = actor.get("resolved")
    if isinstance(resolved_actor, str) and resolved_actor.strip():
        if normalize_identifier(resolved_actor) not in lookup["party"]:
            errors.append(
                f"actor.resolved '{resolved_actor}' is not a supplied party member"
            )
    for position, resource in enumerate(value.get("resources") or []):
        if not isinstance(resource, Mapping):
            continue
        label = f"resources[{position}]"
        owner = resource.get("owner")
        owner_ref = None
        if isinstance(owner, str) and owner.strip():
            owner_ref = _owner_for(lookup, owner)
            if owner_ref is None:
                errors.append(
                    f"{label}.owner '{owner}' is not a supplied character or container id"
                )
        if resource.get("found") is True:
            name = resource.get("resolved_name")
            family = resource.get("family")
            if (
                family is None
                and owner_ref is not None
                and owner_ref["kind"] == "container"
            ):
                # Container reference: the place named as source or
                # destination. It is identified by owner alone.
                if isinstance(name, str) and name.strip():
                    if normalize_identifier(name) not in {
                        normalize_identifier(owner_ref["name"]),
                        normalize_identifier(owner_ref["id"]),
                    }:
                        errors.append(
                            f"{label} names container '{owner_ref['id']}' but "
                            f"resolved_name '{name}' is not that container"
                        )
                continue
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{label} is found but has no resolved_name")
                continue
            if family not in FAMILIES:
                errors.append(f"{label} is found but has no family")
                continue
            if owner_ref is None:
                if isinstance(owner, str) and owner.strip():
                    continue  # already reported as an unknown owner
                errors.append(f"{label} is found but has no owner")
                continue
            key = (
                owner_ref["kind"],
                normalize_identifier(owner_ref["id"]),
                family,
                normalize_identifier(name),
            )
            if key not in lookup["rows"]:
                errors.append(
                    f"{label} claims '{name}' ({family}) is held by "
                    f"'{owner_ref['id']}' but that row is not in the supplied state"
                )

    # Movements are the SLICE half of the contract. Both endpoints must be
    # state identities before code will look at the movement at all; a
    # half-specified movement is the exact shape that commits a one-sided loss.
    for position, movement in enumerate(value.get("movements") or []):
        if not isinstance(movement, Mapping):
            continue
        label = f"movements[{position}]"
        for role in ("source", "destination"):
            endpoint = movement.get(role)
            if not isinstance(endpoint, Mapping):
                continue
            kind = endpoint.get("kind")
            if kind == "external":
                continue
            identifier = endpoint.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                errors.append(
                    f"{label}.{role} needs the exact state name or container id"
                )
                continue
            owner_ref = _owner_for(lookup, identifier)
            if owner_ref is None or owner_ref["kind"] != kind:
                errors.append(
                    f"{label}.{role} '{identifier}' is not a supplied "
                    f"{kind} in the state packet"
                )
        source = movement.get("source")
        family = movement.get("family")
        name = movement.get("resolved_name")
        if (
            isinstance(source, Mapping)
            and source.get("kind") in {"character", "container"}
            and family in FAMILIES
            and isinstance(name, str)
            and name.strip()
        ):
            owner_ref = _owner_for(lookup, str(source.get("id") or ""))
            if owner_ref is not None and owner_ref["kind"] == source.get("kind"):
                key = (
                    owner_ref["kind"],
                    normalize_identifier(owner_ref["id"]),
                    family,
                    normalize_identifier(name),
                )
                if key not in lookup["rows"]:
                    errors.append(
                        f"{label} moves '{name}' ({family}) out of "
                        f"'{owner_ref['id']}' but that row is not there in the "
                        "supplied state"
                    )
    return errors


def _owner_for(
    lookup: Mapping[str, Any], claimed: str
) -> Optional[Dict[str, Any]]:
    """Exact-identity owner lookup: character name, container id, container name."""
    normalized = normalize_identifier(claimed)
    owner = lookup["owners"].get(normalized)
    if owner is not None:
        return owner
    container_ids = lookup["container_names"].get(normalized) or []
    if len(container_ids) == 1:
        return lookup["owners"].get(normalize_identifier(container_ids[0]))
    return None


# ---------------------------------------------------------------------------
# Deterministic facts
# ---------------------------------------------------------------------------


def _state_rows_for(
    lookup: Mapping[str, Any], family: Optional[str], name: Optional[str]
) -> List[Dict[str, Any]]:
    if not isinstance(name, str) or not name.strip():
        return []
    normalized = normalize_identifier(name)
    if family in FAMILIES:
        return list(lookup["rows_by_name"].get((family, normalized)) or [])
    matches: List[Dict[str, Any]] = []
    for candidate_family in FAMILIES:
        matches.extend(lookup["rows_by_name"].get((candidate_family, normalized)) or [])
    return matches


def resource_fact(
    lookup: Mapping[str, Any], resource: Mapping[str, Any]
) -> Dict[str, Any]:
    """Turn one resolved reference into a deterministic, state-backed fact."""
    reference = clean_text(resource.get("reference"))
    claimed_owner = resource.get("owner")
    claimed_owner = claimed_owner if isinstance(claimed_owner, str) else None
    resolved_name = resource.get("resolved_name")
    resolved_name = resolved_name if isinstance(resolved_name, str) else None
    family = resource.get("family") if resource.get("family") in FAMILIES else None
    model_found = resource.get("found") is True
    model_quantity = resource.get("available_quantity")
    if isinstance(model_quantity, bool) or not isinstance(model_quantity, int):
        model_quantity = None

    discrepancies: List[str] = []
    owner_ref: Optional[Dict[str, Any]] = None
    owner_claim_failed = False
    if claimed_owner and claimed_owner.strip():
        owner_ref = _owner_for(lookup, claimed_owner)
        if owner_ref is None:
            # A named holder that does not exist is a resolution failure, not
            # an invitation to re-home the row onto whoever happens to hold a
            # matching name. Fail closed.
            owner_claim_failed = True
            discrepancies.append(CODE_UNKNOWN_OWNER)

    # A container named as the source or destination of the action is a
    # reference to a place, not to a resource row: family is null and owner is
    # the container id. It carries the destination the fixed output contract
    # has no separate field for, so it is resolved as its own fact kind.
    if (
        family is None
        and owner_ref is not None
        and owner_ref["kind"] == "container"
        and (
            resolved_name is None
            or normalize_identifier(resolved_name)
            in {
                normalize_identifier(owner_ref["name"]),
                normalize_identifier(owner_ref["id"]),
            }
        )
    ):
        if not owner_ref.get("accessible", False):
            discrepancies.append(CODE_CONTAINER_NOT_ACCESSIBLE)
        if not model_found:
            discrepancies.append(CODE_ROW_PRESENT)
        if model_quantity is not None:
            discrepancies.append(CODE_MODEL_QUANTITY_DISAGREES)
        ordered_codes = sorted(set(discrepancies))
        return {
            "kind": "container",
            "reference": reference,
            "family": None,
            "resolved_name": owner_ref["name"],
            "claimed_name": resolved_name,
            "claimed_owner": claimed_owner,
            "owner": {
                "kind": "container",
                "id": owner_ref["id"],
                "name": owner_ref["name"],
                "accessible": bool(owner_ref.get("accessible", False)),
            },
            "canonical_key": json.dumps(
                {"container_id": normalize_identifier(owner_ref["id"])},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "available_quantity": None,
            "available_charges": None,
            "model_quantity": model_quantity,
            "found": True,
            "model_found": model_found,
            "model_discrepancy": (
                resource.get("discrepancy")
                if isinstance(resource.get("discrepancy"), str)
                else None
            ),
            "discrepancies": ordered_codes,
            "actionable": bool(owner_ref.get("accessible", False)),
        }

    candidates = [] if owner_claim_failed else _state_rows_for(
        lookup, family, resolved_name
    )
    state_row: Optional[Dict[str, Any]] = None
    if owner_ref is not None and candidates:
        owner_key = (owner_ref["kind"], normalize_identifier(owner_ref["id"]))
        owned = [
            candidate
            for candidate in candidates
            if (
                candidate["owner"]["kind"],
                normalize_identifier(candidate["owner"]["id"]),
            )
            == owner_key
        ]
        if len(owned) == 1:
            state_row = owned[0]
        elif len(owned) > 1:
            discrepancies.append(CODE_AMBIGUOUS_OWNER)
        else:
            # The row exists, but not where the model placed it. Report the
            # real holder when it is unambiguous; never silently accept the
            # claimed holder.
            discrepancies.append(CODE_OWNER_MISMATCH)
            if len(candidates) == 1:
                state_row = candidates[0]
                owner_ref = candidates[0]["owner"]
            else:
                discrepancies.append(CODE_AMBIGUOUS_OWNER)
    elif owner_ref is None and candidates:
        if len(candidates) == 1:
            state_row = candidates[0]
            owner_ref = candidates[0]["owner"]
        else:
            discrepancies.append(CODE_AMBIGUOUS_OWNER)

    if state_row is not None and state_row.get("duplicate") is True:
        discrepancies.append(CODE_AMBIGUOUS_OWNER)
        state_row = None

    # A reference the model reports as absent is legitimately null in every
    # field; only a claimed-present row owes an identity.
    if model_found:
        if resolved_name is None or not resolved_name.strip():
            discrepancies.append(CODE_NAME_MISSING)
        if family is None:
            discrepancies.append(CODE_FAMILY_MISSING)

    found = state_row is not None
    if model_found and not found:
        discrepancies.append(CODE_ROW_ABSENT)
    if found and not model_found:
        discrepancies.append(CODE_ROW_PRESENT)

    available_quantity = state_row["quantity"] if state_row is not None else None
    available_charges = state_row["charges"] if state_row is not None else None
    if found and available_quantity is None:
        discrepancies.append(CODE_MALFORMED_STATE_QUANTITY)
    if (
        found
        and model_quantity is not None
        and available_quantity is not None
        and model_quantity != available_quantity
    ):
        discrepancies.append(CODE_MODEL_QUANTITY_DISAGREES)
    if (
        found
        and owner_ref is not None
        and owner_ref["kind"] == "container"
        and not owner_ref.get("accessible", False)
    ):
        discrepancies.append(CODE_CONTAINER_NOT_ACCESSIBLE)

    state_family = state_row["family"] if state_row is not None else family
    state_name = state_row["name"] if state_row is not None else None
    # continues below with the resource-row fact
    owner_view = (
        {
            "kind": owner_ref["kind"],
            "id": owner_ref["id"],
            "name": owner_ref["name"],
            "accessible": bool(owner_ref.get("accessible", False)),
        }
        if owner_ref is not None
        else {"kind": None, "id": None, "name": None, "accessible": False}
    )
    ordered_codes = sorted(set(discrepancies))
    return {
        "kind": "resource",
        "reference": reference,
        "family": state_family,
        "resolved_name": state_name,
        "claimed_name": resolved_name,
        "claimed_owner": claimed_owner,
        "owner": owner_view,
        "canonical_key": canonical_row_key(
            owner_view["kind"], owner_view["id"], state_family, state_name
        ),
        "available_quantity": available_quantity,
        "available_charges": available_charges,
        "model_quantity": model_quantity,
        "found": found,
        "model_found": model_found,
        "model_discrepancy": (
            resource.get("discrepancy")
            if isinstance(resource.get("discrepancy"), str)
            else None
        ),
        "discrepancies": ordered_codes,
        "actionable": found
        and available_quantity is not None
        and CODE_AMBIGUOUS_OWNER not in ordered_codes
        and CODE_CONTAINER_NOT_ACCESSIBLE not in ordered_codes,
    }


def actor_fact(
    lookup: Mapping[str, Any], resolution: Mapping[str, Any]
) -> Dict[str, Any]:
    """Turn the resolved actor into a deterministic party fact."""
    actor = resolution.get("actor") or {}
    resolved = actor.get("resolved")
    resolved = resolved if isinstance(resolved, str) and resolved.strip() else None
    confidence = (
        actor.get("confidence") if actor.get("confidence") in CONFIDENCE_LEVELS else "low"
    )
    discrepancies: List[str] = []
    member = (
        lookup["party"].get(normalize_identifier(resolved))
        if resolved is not None
        else None
    )
    if resolved is None:
        discrepancies.append(CODE_ACTOR_UNRESOLVED)
    elif member is None:
        discrepancies.append(CODE_ACTOR_NOT_IN_PARTY)
    elif not member.get("present", True):
        discrepancies.append(CODE_ACTOR_NOT_PRESENT)
    if confidence != "high":
        discrepancies.append(CODE_ACTOR_LOW_CONFIDENCE)
    ordered_codes = sorted(set(discrepancies))
    return {
        "resolved": member["name"] if member is not None else None,
        "claimed": resolved,
        "confidence": confidence,
        "in_party": member is not None,
        "present": bool(member.get("present", True)) if member is not None else False,
        "discrepancies": ordered_codes,
        "actionable": member is not None
        and bool(member.get("present", True))
        and confidence == "high",
    }


# ---------------------------------------------------------------------------
# Stage 2: code turns mapped movements into SLICES
#
# No prose is read here. The mapper supplies structured endpoints; this code
# verifies each endpoint against the state index, re-reads the moved row's
# quantity from state, and refuses to build a slice it cannot back. What it
# cannot back becomes an ``unresolved`` entry with a machine reason.
# ---------------------------------------------------------------------------


def _slice_endpoint(
    lookup: Mapping[str, Any],
    value: Any,
    *,
    allow_external: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Resolve one movement endpoint to a state identity, or give a reason."""
    if not isinstance(value, Mapping):
        return None, SLICE_ENDPOINT_MALFORMED
    kind = value.get("kind")
    identifier = value.get("id")
    identifier = identifier if isinstance(identifier, str) else ""
    if kind == "external":
        if not allow_external:
            return None, SLICE_ENDPOINT_EXTERNAL_NOT_ALLOWED
        return (
            {
                "kind": "external",
                "id": clean_text(identifier) or "external",
                "name": clean_text(identifier) or "external",
                "accessible": True,
            },
            None,
        )
    if kind not in {"character", "container"}:
        return None, SLICE_ENDPOINT_KIND_INVALID
    if not identifier.strip():
        return None, SLICE_ENDPOINT_MALFORMED
    owner = _owner_for(lookup, identifier)
    if owner is None or owner["kind"] != kind:
        return None, SLICE_ENDPOINT_NOT_IN_STATE
    if kind == "container" and not owner.get("accessible", False):
        return None, SLICE_CONTAINER_NOT_ACCESSIBLE
    return (
        {
            "kind": owner["kind"],
            "id": owner["id"],
            "name": owner["name"],
            "accessible": bool(owner.get("accessible", True)),
        },
        None,
    )


def _endpoint_identity(endpoint: Optional[Mapping[str, Any]]) -> Tuple[str, str]:
    if not isinstance(endpoint, Mapping):
        return ("", "")
    return (
        str(endpoint.get("kind") or ""),
        normalize_identifier(endpoint.get("id")),
    )


def derive_slices(
    lookup: Mapping[str, Any],
    resolution: Mapping[str, Any],
    *,
    actor: Optional[str] = None,
    action_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the SLICE list code acts on from one validated resolution.

    Returns {"slices": [...], "unresolved": [...]}. Every slice carries both
    endpoints by construction; anything that cannot be pinned to state stays in
    ``unresolved`` with a reason so the caller can fail closed instead of
    committing half a movement.
    """
    slices: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    for position, movement in enumerate(resolution.get("movements") or []):
        slice_id = f"m{position}"
        phrase = clean_text(
            movement.get("reference") if isinstance(movement, Mapping) else ""
        )
        provenance = {"action_index": action_index, "phrase": phrase}

        def _reject(reason: str) -> None:
            unresolved.append(
                {
                    "slice_id": slice_id,
                    "reason": reason,
                    "provenance": dict(provenance),
                }
            )

        if not isinstance(movement, Mapping):
            _reject(SLICE_ENDPOINT_MALFORMED)
            continue
        kind = movement.get("kind")
        if kind not in SLICE_KINDS:
            _reject(SLICE_KIND_INVALID)
            continue
        family = movement.get("family")
        if family not in FAMILIES:
            _reject(SLICE_FAMILY_INVALID)
            continue
        claimed_name = movement.get("resolved_name")
        if not isinstance(claimed_name, str) or not claimed_name.strip():
            _reject(SLICE_NAME_MISSING)
            continue

        source, source_reason = _slice_endpoint(
            lookup,
            movement.get("source"),
            allow_external=kind in _EXTERNAL_SOURCE_KINDS,
        )
        if source is None:
            _reject(source_reason or SLICE_ENDPOINT_MALFORMED)
            continue
        destination, destination_reason = _slice_endpoint(
            lookup,
            movement.get("destination"),
            allow_external=kind in _EXTERNAL_DESTINATION_KINDS,
        )
        if destination is None:
            _reject(destination_reason or SLICE_ENDPOINT_MALFORMED)
            continue
        if _endpoint_identity(source) == _endpoint_identity(destination):
            _reject(SLICE_ENDPOINTS_IDENTICAL)
            continue
        if source["kind"] == "external" and destination["kind"] == "external":
            _reject(SLICE_BOTH_ENDPOINTS_EXTERNAL)
            continue

        canonical_name = clean_text(claimed_name)
        quantity: Optional[int] = None
        row_identity: Optional[str] = None
        if source["kind"] == "external":
            # Nothing tracked leaves state, so there is no state row to read.
            row_identity = canonical_row_key(
                destination["kind"], destination["id"], family, canonical_name
            )
        else:
            row = lookup["rows"].get(
                (
                    source["kind"],
                    normalize_identifier(source["id"]),
                    family,
                    normalize_identifier(canonical_name),
                )
            )
            if row is None:
                _reject(SLICE_ROW_NOT_AT_SOURCE)
                continue
            if row.get("duplicate") is True:
                _reject(SLICE_ROW_AMBIGUOUS)
                continue
            canonical_name = row["name"]
            quantity = row["quantity"]
            if quantity is None:
                _reject(SLICE_QUANTITY_UNREADABLE)
                continue
            row_identity = canonical_row_key(
                source["kind"], source["id"], family, canonical_name
            )

        stated = movement.get("stated_quantity")
        if stated is not None and (
            isinstance(stated, bool) or not isinstance(stated, int) or stated <= 0
        ):
            _reject(SLICE_STATED_QUANTITY_INVALID)
            continue

        slices.append(
            {
                "slice_id": slice_id,
                "kind": kind,
                "actor": actor,
                "source": source,
                "destination": destination,
                "family": family,
                "canonical_name": canonical_name,
                "row_identity": row_identity,
                # Quantity ALWAYS comes from the state row at the source.
                "quantity": quantity,
                # What the prose asserted, carried for comparison only. It is
                # never promoted into ``quantity``.
                "stated_quantity": stated,
                "provenance": dict(provenance),
            }
        )
    return {"slices": slices, "unresolved": unresolved}


# ---------------------------------------------------------------------------
# Stage 4: code self-validates slices
#
# This gate is applied to EVERY slice, whoever built it. A slice derived by
# code has no privileged path through it.
# ---------------------------------------------------------------------------


def slice_contract_errors(slices: Any) -> List[str]:
    """Return deterministic violations in a slice list."""
    errors: List[str] = []
    seen_ids = set()
    produced: Dict[Tuple[str, str], int] = {}
    for position, entry in enumerate(slices or ()):
        label = f"slice[{position}]"
        if not isinstance(entry, Mapping):
            errors.append(f"{label} is not a slice object")
            continue
        slice_id = entry.get("slice_id")
        if not isinstance(slice_id, str) or not slice_id.strip():
            errors.append(f"{label} has no slice_id")
        elif slice_id in seen_ids:
            errors.append(f"{label} {SLICE_DUPLICATE_ID}")
        else:
            seen_ids.add(slice_id)
        kind = entry.get("kind")
        if kind not in SLICE_KINDS:
            errors.append(f"{label} {SLICE_KIND_INVALID}")
        if entry.get("family") not in FAMILIES:
            errors.append(f"{label} {SLICE_FAMILY_INVALID}")
        name = entry.get("canonical_name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{label} {SLICE_NAME_MISSING}")
        source = entry.get("source")
        destination = entry.get("destination")
        for role, endpoint in (("source", source), ("destination", destination)):
            if not isinstance(endpoint, Mapping):
                errors.append(f"{label}.{role} {SLICE_ENDPOINT_MALFORMED}")
                continue
            if endpoint.get("kind") not in ENDPOINT_KINDS:
                errors.append(f"{label}.{role} {SLICE_ENDPOINT_KIND_INVALID}")
            if not str(endpoint.get("id") or "").strip():
                errors.append(f"{label}.{role} {SLICE_ENDPOINT_MALFORMED}")
        if isinstance(source, Mapping) and source.get("kind") == "external":
            if kind not in _EXTERNAL_SOURCE_KINDS:
                errors.append(f"{label}.source {SLICE_ENDPOINT_EXTERNAL_NOT_ALLOWED}")
        if isinstance(destination, Mapping) and destination.get("kind") == "external":
            if kind not in _EXTERNAL_DESTINATION_KINDS:
                errors.append(
                    f"{label}.destination {SLICE_ENDPOINT_EXTERNAL_NOT_ALLOWED}"
                )
        if _endpoint_identity(source) == _endpoint_identity(destination):
            errors.append(f"{label} {SLICE_ENDPOINTS_IDENTICAL}")
        quantity = entry.get("quantity")
        external_source = (
            isinstance(source, Mapping) and source.get("kind") == "external"
        )
        if (
            external_source
            and isinstance(destination, Mapping)
            and destination.get("kind") == "external"
        ):
            errors.append(f"{label} {SLICE_BOTH_ENDPOINTS_EXTERNAL}")
        if external_source:
            if quantity is not None:
                errors.append(f"{label} {SLICE_QUANTITY_UNREADABLE}")
        elif isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
            errors.append(f"{label} {SLICE_QUANTITY_UNREADABLE}")
        stated = entry.get("stated_quantity")
        if stated is not None and (
            isinstance(stated, bool) or not isinstance(stated, int) or stated <= 0
        ):
            errors.append(f"{label} {SLICE_STATED_QUANTITY_INVALID}")
        if not isinstance(entry.get("provenance"), Mapping):
            errors.append(f"{label} has no provenance")
        if (
            isinstance(source, Mapping)
            and not external_source
            and entry.get("row_identity")
            != canonical_row_key(
                source.get("kind"),
                source.get("id"),
                entry.get("family"),
                name,
            )
        ):
            errors.append(f"{label} row_identity does not match its source row")
        # Dependency ordering: a slice may only draw from a row an earlier
        # slice created, never from one produced later in the same batch.
        if isinstance(destination, Mapping) and entry.get("family") in FAMILIES:
            key = (
                _endpoint_identity(destination)[0]
                + "\x00"
                + _endpoint_identity(destination)[1],
                entry.get("family") + "\x00" + normalize_identifier(name),
            )
            produced.setdefault(key, position)
    for position, entry in enumerate(slices or ()):
        if not isinstance(entry, Mapping):
            continue
        source = entry.get("source")
        name = entry.get("canonical_name")
        if not isinstance(source, Mapping) or source.get("kind") == "external":
            continue
        if entry.get("family") not in FAMILIES:
            continue
        key = (
            _endpoint_identity(source)[0] + "\x00" + _endpoint_identity(source)[1],
            entry.get("family") + "\x00" + normalize_identifier(name),
        )
        producer = produced.get(key)
        if producer is not None and producer > position and entry.get("quantity") == 0:
            errors.append(f"slice[{position}] {SLICE_DEPENDENCY_ORDER}")
    return errors


def resolution_facts(
    snapshot: Mapping[str, Any],
    resolution: Mapping[str, Any],
    index: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Derive every deterministic fact code needs from one resolution.

    The result never contains a quantity or charge value that did not come
    from ``snapshot``. ``blocking_problem`` is passed through untouched: it is
    player-facing prose the narrator voices, not a control signal.
    """
    lookup = index if index is not None else index_snapshot(snapshot)
    actor = actor_fact(lookup, resolution)
    facts = [
        resource_fact(lookup, resource)
        for resource in resolution.get("resources") or []
        if isinstance(resource, Mapping)
    ]
    intent = resolution.get("intent") if resolution.get("intent") in INTENTS else "other"
    blocking_problem = resolution.get("blocking_problem")
    blocking_problem = (
        blocking_problem
        if isinstance(blocking_problem, str) and blocking_problem.strip()
        else None
    )
    missing = [fact for fact in facts if not fact["found"]]
    codes = sorted(
        {code for fact in facts for code in fact["discrepancies"]}
        | set(actor["discrepancies"])
    )
    derived = derive_slices(lookup, resolution, actor=actor["resolved"])
    slices = derived["slices"]
    unresolved = derived["unresolved"]
    # Stage 4: the identical gate runs over code-derived slices. There is no
    # privileged path for slices this module built itself.
    slice_errors = slice_contract_errors(slices)
    return {
        "intent": intent,
        "actor": actor,
        "facts": facts,
        "missing": missing,
        "slices": slices,
        "unresolved": unresolved,
        "slice_errors": slice_errors,
        "blocking_problem": blocking_problem,
        "discrepancies": codes,
        "actionable": actor["actionable"]
        and bool(facts)
        and all(fact["actionable"] for fact in facts)
        and not unresolved
        and not slice_errors,
    }


# ---------------------------------------------------------------------------
# Decision-point queries
#
# These are the ONLY accessors gameplay code uses to ask what an accepted
# response referred to. They read the derived facts above; they never look at
# prose. A caller that has no facts gets None/empty and must not fall back to
# reading words.
# ---------------------------------------------------------------------------


class ResolvedTurn:
    """Immutable per-turn lookup from accepted prose to derived facts.

    Pure by construction: it holds already-derived facts and does no I/O. The
    runtime service in core/managers/inventory_resolution_service.py fills one
    of these lazily; deterministic checks can build one directly from
    ``resolution_facts`` output.
    """

    __slots__ = ("_entries",)

    def __init__(self, entries: Optional[Mapping[str, Any]] = None) -> None:
        self._entries: Dict[str, Any] = {}
        for text, facts in (entries or {}).items():
            self._entries[prose_key(text)] = facts

    def facts_for(self, text: Any) -> Optional[Dict[str, Any]]:
        """Return derived facts for one accepted prose string, or None."""
        return self._entries.get(prose_key(text))


def prose_key(text: Any) -> str:
    """Stable cache identity for one accepted prose string.

    This is a dictionary key over the WHOLE string, never a test for words
    inside it. Two callers asking about byte-identical prose share one answer.
    """
    return " ".join(str(text if text is not None else "").split()).casefold()


def facts_for(resolution: Any, text: Any) -> Optional[Dict[str, Any]]:
    """Ask any resolution provider for the facts behind one prose string.

    None means NO CLAIM: the provider is absent, out of budget, or could not
    produce a state-backed answer. No claim is never permission. Callers MUST
    fail closed on it -- see ``unverified_movement_refusal``.
    """
    if resolution is None:
        return None
    getter = getattr(resolution, "facts_for", None)
    if getter is None:
        return None
    facts = getter(text)
    return facts if isinstance(facts, Mapping) else None


# The single diegetic refusal used everywhere a resource would otherwise move
# without a state-backed claim behind it. It is phrased for the narrator and
# for the response-regeneration loop, never as a system error.
UNVERIFIED_MOVEMENT_REFUSAL = (
    "This response moves belongings, but what it moves could not be checked "
    "against the party's actual inventories and containers, so nothing was "
    "applied. State the action again naming exactly who acts, which item, "
    "ammunition, or coin moves, and both where it comes from and where it "
    "goes."
)


def unverified_movement_refusal(detail: Any = None) -> str:
    """Return the shared refusal, optionally naming the machine reason."""
    reason = clean_text(detail)
    if not reason:
        return UNVERIFIED_MOVEMENT_REFUSAL
    return f"{UNVERIFIED_MOVEMENT_REFUSAL} (unverified: {reason})"


def movement_claim_fault(resolution: Any, text: Any) -> Optional[str]:
    """Return a refusal reason when this prose has no committable claim.

    Returns None only when a real, state-backed resolution exists AND every
    movement it named survived the deterministic slice gate. Every other
    outcome -- provider outage, exhausted budget, unreadable sheet, contract
    failure, an endpoint or row that is not in state -- yields a reason and
    the caller must refuse.
    """
    facts = facts_for(resolution, text)
    if facts is None:
        return "no state-backed resolution was available"
    faults = slice_faults(facts)
    if faults:
        return "; ".join(faults)
    return None


def resolved_actor(facts: Any) -> Optional[str]:
    """Return the state-backed actor name, or None when it is not usable."""
    if not isinstance(facts, Mapping):
        return None
    actor = facts.get("actor")
    if not isinstance(actor, Mapping) or not actor.get("actionable"):
        return None
    name = actor.get("resolved")
    return name if isinstance(name, str) and name.strip() else None


def resolved_intent(facts: Any) -> Optional[str]:
    """Return the classified intent, or None when nothing was resolved."""
    if not isinstance(facts, Mapping):
        return None
    intent = facts.get("intent")
    return intent if intent in INTENTS else None


def resource_facts(facts: Any) -> Tuple[Dict[str, Any], ...]:
    """Return the resolved resource-row facts (never container references)."""
    if not isinstance(facts, Mapping):
        return ()
    return tuple(
        fact
        for fact in facts.get("facts") or []
        if isinstance(fact, Mapping) and fact.get("kind") == "resource"
    )


# ---------------------------------------------------------------------------
# Slice accessors
#
# These are the ONLY way gameplay code reads a movement. Each one reads
# structured slice fields; none of them reads the phrase.
# ---------------------------------------------------------------------------


def slices_of(facts: Any) -> Tuple[Dict[str, Any], ...]:
    """Return the verified slices for one resolution."""
    if not isinstance(facts, Mapping):
        return ()
    return tuple(
        entry
        for entry in facts.get("slices") or ()
        if isinstance(entry, Mapping)
    )


def unresolved_of(facts: Any) -> Tuple[Dict[str, Any], ...]:
    """Return the movements code refused to turn into slices, with reasons."""
    if not isinstance(facts, Mapping):
        return ()
    return tuple(
        entry
        for entry in facts.get("unresolved") or ()
        if isinstance(entry, Mapping)
    )


def slice_faults(facts: Any) -> Tuple[str, ...]:
    """Return every reason this resolution's movements are not committable.

    A non-empty result means code must refuse: something the mapper named
    could not be pinned to state, or a slice failed the deterministic gate.
    """
    if not isinstance(facts, Mapping):
        return ()
    reasons = [
        str(entry.get("reason") or "slice_unresolved")
        for entry in unresolved_of(facts)
    ]
    reasons.extend(
        str(value) for value in facts.get("slice_errors") or () if str(value)
    )
    return tuple(dict.fromkeys(reasons))


def party_transfer_slices(facts: Any) -> Tuple[Dict[str, Any], ...]:
    """Return slices whose BOTH endpoints are party characters.

    A give/store/sell slice carries a source and a destination by
    construction, so the counterpart half exists whether or not the actor
    happens to be the current holder. This is what stops a one-sided loss from
    committing when the giver is also the speaker.
    """
    result = []
    for entry in slices_of(facts):
        source = entry.get("source") or {}
        destination = entry.get("destination") or {}
        if source.get("kind") != "character" or destination.get("kind") != "character":
            continue
        if normalize_identifier(source.get("id")) == normalize_identifier(
            destination.get("id")
        ):
            continue
        result.append(entry)
    return tuple(result)


def container_slices(facts: Any) -> Tuple[Dict[str, Any], ...]:
    """Return slices with a container on either end (a storage movement)."""
    return tuple(
        entry
        for entry in slices_of(facts)
        if (entry.get("source") or {}).get("kind") == "container"
        or (entry.get("destination") or {}).get("kind") == "container"
    )


def slice_character_endpoints(facts: Any) -> Tuple[str, ...]:
    """Return every party character named as an endpoint by a slice."""
    names = []
    for entry in slices_of(facts):
        for role in ("source", "destination"):
            endpoint = entry.get(role) or {}
            if endpoint.get("kind") == "character":
                identifier = endpoint.get("id")
                if isinstance(identifier, str) and identifier.strip():
                    names.append(identifier)
    return tuple(dict.fromkeys(names))


def slice_identities(facts: Any) -> Tuple[Tuple[str, str], ...]:
    """Return (family, normalized name) for every identity a slice moves."""
    identities = []
    for entry in slices_of(facts):
        family = entry.get("family")
        name = entry.get("canonical_name")
        if family in FAMILIES and isinstance(name, str) and name.strip():
            identities.append((family, normalize_identifier(name)))
    return tuple(dict.fromkeys(identities))


def slice_mentions_identity(facts: Any, family: Any, name: Any) -> bool:
    """True when a slice moves this exact state row identity."""
    if family not in FAMILIES:
        return False
    return (family, normalize_identifier(name)) in set(slice_identities(facts))


def permuted_slice_identities(facts: Any) -> Tuple[Tuple[str, str], ...]:
    """Return identities whose phrasing asserted more than state holds.

    UNDERFLOW / ITEM-PERMUTATION GUARD. The state row stays authoritative and
    the phrased number is discarded for that identity, so no phrased quantity
    can ever become a required concrete delta. This is a recorded conflict,
    not a refusal: the wand with one charge is still the wand.
    """
    identities = []
    for entry in slices_of(facts):
        stated = entry.get("stated_quantity")
        quantity = entry.get("quantity")
        if isinstance(stated, bool) or not isinstance(stated, int):
            continue
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            continue
        if stated <= quantity:
            continue
        family = entry.get("family")
        name = entry.get("canonical_name")
        if family in FAMILIES and isinstance(name, str) and name.strip():
            identities.append((family, normalize_identifier(name)))
    return tuple(dict.fromkeys(identities))


def outbound_slice_names(
    facts: Any, *, family: Any, character: Any
) -> Tuple[str, ...]:
    """Return the normalized row names this character SENDS AWAY in one family.

    A row leaves a character when a slice names that character as its source:
    given away, stored, sold, discarded, or consumed. The answer is read from
    the slice's structured endpoints and canonical identity -- never from the
    phrase that produced it -- so a decrement can be checked against what the
    mapper actually resolved instead of against words in the narration.
    """
    target = normalize_identifier(character)
    if not target or family not in FAMILIES:
        return ()
    names = []
    for entry in slices_of(facts):
        if entry.get("family") != family:
            continue
        source = entry.get("source") or {}
        if source.get("kind") != "character":
            continue
        if normalize_identifier(source.get("id")) != target:
            continue
        name = entry.get("canonical_name")
        if isinstance(name, str) and name.strip():
            names.append(normalize_identifier(name))
    return tuple(dict.fromkeys(names))


def stated_slice_quantities(
    facts: Any, character: Any
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    """Return (removals, acquisitions) this character's slices assert.

    The numbers are the mapper's ``stated_quantity`` -- what the prose
    asserted, structurally reported rather than pattern-matched out of the
    sentence. Callers compare them against concrete image deltas; they never
    treat them as the amount actually available.

    Slices with a container endpoint are EXCLUDED. Those legs are owned and
    conserved by the storage transaction against the real container, so
    charging them to the character batch as well would demand the same
    movement twice.
    """
    target = normalize_identifier(character)
    removals: Dict[Tuple[str, str], int] = {}
    acquisitions: Dict[Tuple[str, str], int] = {}
    if not target:
        return removals, acquisitions
    permuted = set(permuted_slice_identities(facts))
    for entry in slices_of(facts):
        stated = entry.get("stated_quantity")
        if isinstance(stated, bool) or not isinstance(stated, int) or stated <= 0:
            continue
        family = entry.get("family")
        name = entry.get("canonical_name")
        if family not in FAMILIES or not isinstance(name, str) or not name.strip():
            continue
        key = (family, normalize_identifier(name))
        if key in permuted:
            # The phrasing contradicts the real row; state wins and the
            # phrased number contributes nothing.
            continue
        source = entry.get("source") or {}
        destination = entry.get("destination") or {}
        if "container" in {source.get("kind"), destination.get("kind")}:
            continue
        if source.get("kind") == "character" and normalize_identifier(
            source.get("id")
        ) == target:
            removals[key] = removals.get(key, 0) + stated
        if destination.get("kind") == "character" and normalize_identifier(
            destination.get("id")
        ) == target:
            acquisitions[key] = acquisitions.get(key, 0) + stated
    return removals, acquisitions
