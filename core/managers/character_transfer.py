# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Atomic adapter for concrete character-to-character transfer deltas."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.managers.effects_runtime import prepare_character_with_effects
from utils.inventory_integrity import (
    consolidate_equipment_rows,
    inventory_metadata,
    normalize_inventory_name,
)
from updates.update_character_info import (
    CharacterMutationPlan,
    _field_change_facts,
    execute_character_mutation_plans,
)
from utils.enhanced_logger import warning


_DENOMINATIONS = {"gold": 100, "silver": 10, "copper": 1}
class CharacterTransferError(RuntimeError):
    """A character batch could not be applied without guessing."""


@dataclass(frozen=True)
class PreparedCharacterAction:
    index: int
    action: Mapping[str, Any]
    changes: str
    plan: CharacterMutationPlan


@dataclass(frozen=True)
class AssetDelta:
    family: str
    name: str
    quantity: int
    metadata: str

    @property
    def lookup_key(self) -> Tuple[str, str]:
        return self.family, self.name


def _normalized_name(value: Any) -> str:
    return normalize_inventory_name(value)


def _strict_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CharacterTransferError(f"{label} must be a nonnegative integer")
    return value


def _currency_value(sheet: Mapping[str, Any]) -> int:
    currency = sheet.get("currency") or {}
    if not isinstance(currency, dict):
        raise CharacterTransferError("currency must be an object")
    total = 0
    for denomination, multiplier in _DENOMINATIONS.items():
        total += (
            _strict_nonnegative_int(
                currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            * multiplier
        )
    return total


def _rows_by_name(
    sheet: Mapping[str, Any],
    field: str,
    name_field: str,
) -> Dict[str, Mapping[str, Any]]:
    rows = sheet.get(field) or []
    if not isinstance(rows, list):
        raise CharacterTransferError(f"{field} must be an array")
    if field == "equipment":
        try:
            rows, _advisories = consolidate_equipment_rows(rows)
        except ValueError as exc:
            raise CharacterTransferError(str(exc)) from exc
    indexed: Dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise CharacterTransferError(f"{field} contains a non-object row")
        name = _normalized_name(row.get(name_field))
        if not name:
            raise CharacterTransferError(f"{field} contains an unnamed row")
        if name in indexed:
            raise CharacterTransferError(f"{field} contains ambiguous duplicate names")
        _strict_nonnegative_int(row.get("quantity", 1), f"{field}.{name}.quantity")
        indexed[name] = row
    return indexed


def _mechanical_metadata(row: Mapping[str, Any], name_field: str) -> str:
    return inventory_metadata(row, name_field, omit_ownership_local=True)


def _t052_normalized_metadata(metadata: str) -> str:
    """Compare mechanics after removing T052-owned display categorization.

    T052 may normalize ``item_type`` while a character mutation plan is being
    prepared.  A removed item has no post-image row on the giver side, so its
    pre-validation category cannot be rewritten to match the receiver's final
    prepared row.  Category is not the item's mechanical payload; every other
    field remains part of the exact conservation check.
    """
    value = json.loads(metadata)
    value.pop("item_type", None)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _row_deltas(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    family: str,
    field: str,
    name_field: str,
) -> List[AssetDelta]:
    old = _rows_by_name(before, field, name_field)
    new = _rows_by_name(after, field, name_field)
    deltas = []
    for name in sorted(set(old) | set(new)):
        old_row = old.get(name)
        new_row = new.get(name)
        old_quantity = int(old_row.get("quantity", 1)) if old_row else 0
        new_quantity = int(new_row.get("quantity", 1)) if new_row else 0
        quantity = new_quantity - old_quantity
        if not quantity:
            continue
        identity_row = old_row if quantity < 0 else new_row
        deltas.append(
            AssetDelta(
                family=family,
                name=name,
                quantity=quantity,
                metadata=_mechanical_metadata(identity_row, name_field),
            )
        )
    return deltas


def concrete_asset_deltas_between(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> Tuple[AssetDelta, ...]:
    """Project concrete transfer-relevant facts between two state images."""
    deltas: List[AssetDelta] = []
    currency_delta = _currency_value(after) - _currency_value(before)
    if currency_delta:
        deltas.append(AssetDelta("currency", "currency", currency_delta, "currency"))
    deltas.extend(
        _row_deltas(
            before,
            after,
            family="equipment",
            field="equipment",
            name_field="item_name",
        )
    )
    deltas.extend(
        _row_deltas(
            before,
            after,
            family="ammunition",
            field="ammunition",
            name_field="name",
        )
    )
    return tuple(deltas)


def concrete_asset_deltas(plan: CharacterMutationPlan) -> Tuple[AssetDelta, ...]:
    """Project only final concrete transfer-relevant before/after facts."""
    return concrete_asset_deltas_between(plan.pre_image, plan.post_image)


def _candidate_components(
    prepared: Sequence[PreparedCharacterAction],
) -> Tuple[Tuple[int, ...], ...]:
    deltas = {item.index: concrete_asset_deltas(item.plan) for item in prepared}
    paths = {item.index: item.plan.canonical_path for item in prepared}
    edges = {item.index: set() for item in prepared}
    by_lookup: Dict[Tuple[str, str], List[Tuple[int, AssetDelta]]] = {}
    for index, values in deltas.items():
        for delta in values:
            by_lookup.setdefault(delta.lookup_key, []).append((index, delta))
    for values in by_lookup.values():
        negative = {index for index, delta in values if delta.quantity < 0}
        positive = {index for index, delta in values if delta.quantity > 0}
        for left in negative:
            for right in positive:
                if left != right and paths[left] != paths[right]:
                    edges[left].add(right)
                    edges[right].add(left)

    components = []
    remaining = set(edges)
    while remaining:
        start = min(remaining)
        stack = [start]
        component = set()
        while stack:
            index = stack.pop()
            if index in component:
                continue
            component.add(index)
            stack.extend(edges[index] - component)
        remaining -= component
        if len(component) >= 2 and any(edges[index] for index in component):
            components.append(tuple(sorted(component)))
    return tuple(sorted(components, key=lambda value: value[0]))


def _batch_transfer_shape_mismatch(
    prepared: Sequence[PreparedCharacterAction],
) -> Optional[str]:
    """Detect transfer-shaped batches that exact-key graphing would miss."""
    if len({item.plan.canonical_path for item in prepared}) < 2:
        return None

    all_deltas = {
        item.index: concrete_asset_deltas(item.plan) for item in prepared
    }
    transfer_deltas = {
        index: tuple(
            delta
            for delta in deltas
            if delta.family in {"equipment", "ammunition"}
        )
        for index, deltas in all_deltas.items()
    }
    negative = [
        (index, delta)
        for index, deltas in transfer_deltas.items()
        for delta in deltas
        if delta.quantity < 0
    ]
    positive = [
        (index, delta)
        for index, deltas in transfer_deltas.items()
        for delta in deltas
        if delta.quantity > 0
    ]

    if negative and positive:
        unpaired = []
        for index, delta in negative:
            if not any(
                other_index != index and other.lookup_key == delta.lookup_key
                for other_index, other in positive
            ):
                unpaired.append(delta.lookup_key)
        for index, delta in positive:
            if not any(
                other_index != index and other.lookup_key == delta.lookup_key
                for other_index, other in negative
            ):
                unpaired.append(delta.lookup_key)
        if unpaired:
            labels = ", ".join(
                f"{family} {name}" for family, name in sorted(set(unpaired))
            )
            return (
                "opposite-direction equipment/ammunition deltas use "
                f"unpaired concrete identities: {labels}"
            )

    no_op_indices = [index for index, deltas in all_deltas.items() if not deltas]
    if no_op_indices and any(transfer_deltas.values()):
        return (
            "a character asset no-op appears beside a nonzero equipment or "
            "ammunition delta"
        )
    return None


def _correction_with_canonical_source_names(
    mismatch: str,
    prepared: Sequence[PreparedCharacterAction],
) -> str:
    """Add only exact, already-persisted outgoing row names to a correction."""
    names = set()
    outgoing = []
    for item in prepared:
        for delta in concrete_asset_deltas(item.plan):
            if delta.quantity >= 0 or delta.family not in {
                "equipment",
                "ammunition",
            }:
                continue
            field, name_field = (
                ("equipment", "item_name")
                if delta.family == "equipment"
                else ("ammunition", "name")
            )
            rows = item.plan.pre_image.get(field) or []
            matches = [
                row
                for row in rows
                if isinstance(row, dict)
                and _normalized_name(row.get(name_field)) == delta.name
            ]
            if len(matches) == 1:
                exact_name = matches[0].get(name_field)
                if isinstance(exact_name, str) and exact_name.strip():
                    names.add(
                        f"{delta.family} {name_field}="
                        f"{json.dumps(exact_name.strip(), ensure_ascii=False)}"
                    )
                    outgoing.append(
                        (item, delta, matches[0], field, name_field, exact_name.strip())
                    )
    if not names:
        return mismatch
    enriched = (
        f"{mismatch}. Canonical source-row names from the giver's current "
        f"sheet: {', '.join(sorted(names))}. Receiving rows must reuse these "
        "exact names; do not abbreviate, pluralize, or rename them"
    )
    if (
        len(outgoing) != 1
        or len(prepared) != 2
        or len({item.plan.canonical_path for item in prepared}) != 2
    ):
        return enriched

    giver, delta, source_row, field, name_field, exact_name = outgoing[0]
    receivers = [item for item in prepared if item.index != giver.index]
    if len(receivers) != 1:
        return enriched
    receiver = receivers[0]
    receiver_rows = receiver.plan.pre_image.get(field) or []
    if not isinstance(receiver_rows, list):
        return enriched
    receiver_matches = [
        row
        for row in receiver_rows
        if isinstance(row, dict)
        and _normalized_name(row.get(name_field)) == _normalized_name(exact_name)
    ]
    if len(receiver_matches) > 1:
        return enriched
    try:
        giver_current = _strict_nonnegative_int(
            source_row.get("quantity", 1),
            f"{field}.{delta.name}.quantity",
        )
        receiver_current = (
            _strict_nonnegative_int(
                receiver_matches[0].get("quantity", 1),
                f"{field}.{delta.name}.quantity",
            )
            if receiver_matches
            else 0
        )
    except CharacterTransferError:
        return enriched
    amount = -delta.quantity
    giver_final = giver_current - amount
    receiver_final = receiver_current + amount
    if amount <= 0 or giver_final < 0:
        return enriched
    return (
        f"{enriched}. Deterministic quantity facts for this exact transfer: "
        f"{giver.plan.character_name} current {giver_current}, removes {amount}, "
        f"required final {giver_final}; {receiver.plan.character_name} current "
        f"{receiver_current}, receives {amount}, required final {receiver_final}. "
        "Returned absolute final quantities must match these required finals exactly"
    )


def _explicit_removal_contract_mismatch(
    prepared: Sequence[PreparedCharacterAction],
) -> Optional[str]:
    """Check only explicit numbered currency/ammunition removal statements."""
    currency_pattern = re.compile(
        r"\b(?:removed|used|expended)\s+(\d+)\s+"
        r"(gold|silver|copper)(?:\s+(?:coin|coins|piece|pieces))?\b",
        re.IGNORECASE,
    )
    for item in prepared:
        text = item.changes
        stated_currency: Dict[str, int] = {}
        for amount, denomination in currency_pattern.findall(text):
            key = denomination.casefold()
            stated_currency[key] = stated_currency.get(key, 0) + int(amount)
        before_currency = item.plan.pre_image.get("currency") or {}
        after_currency = item.plan.post_image.get("currency") or {}
        for denomination, stated in sorted(stated_currency.items()):
            before = _strict_nonnegative_int(
                before_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            after = _strict_nonnegative_int(
                after_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            actual = before - after
            if actual != stated:
                return (
                    f"stated removal of {stated} {denomination} produced "
                    f"a concrete removal of {actual} {denomination}"
                )

        before_ammo = _rows_by_name(item.plan.pre_image, "ammunition", "name")
        after_ammo = _rows_by_name(item.plan.post_image, "ammunition", "name")
        for name, before_row in sorted(before_ammo.items()):
            variants = {name}
            if name.endswith("s") and len(name) > 1:
                variants.add(name[:-1])
            ammo_pattern = re.compile(
                r"\b(?:removed|used|expended)\s+(\d+)\s+(?:"
                + "|".join(
                    re.escape(value) for value in sorted(variants, key=len, reverse=True)
                )
                + r")\b",
                re.IGNORECASE,
            )
            stated_amounts = [int(value) for value in ammo_pattern.findall(text)]
            if not stated_amounts:
                continue
            stated = sum(stated_amounts)
            before = _strict_nonnegative_int(
                before_row.get("quantity", 1),
                f"ammunition.{name}.quantity",
            )
            after_row = after_ammo.get(name)
            after = (
                _strict_nonnegative_int(
                    after_row.get("quantity", 1),
                    f"ammunition.{name}.quantity",
                )
                if after_row
                else 0
            )
            actual = before - after
            if actual != stated:
                return (
                    f"stated removal of {stated} {name} produced a concrete "
                    f"removal of {actual} {name}"
                )
    return None


_ACQUISITION_VERBS = r"(?:added|received|gained|acquired|collected|earned|obtained)"


def _effective_same_character_asset_deltas(
    prepared: Sequence[PreparedCharacterAction],
):
    """Project one effective final per character from independently made plans.

    This mirrors the response transaction's deterministic merge rule for the
    three resource families. Unchanged candidates contribute nothing,
    identical finals deduplicate, and competing finals are rejected.
    """
    effective = {}
    by_path: Dict[str, List[PreparedCharacterAction]] = {}
    for item in prepared:
        by_path.setdefault(item.plan.canonical_path, []).append(item)

    for path, items in by_path.items():
        before = items[0].plan.pre_image
        if any(item.plan.pre_image != before for item in items[1:]):
            raise CharacterTransferError(
                "same-character actions do not share one pre-image"
            )
        before_currency = before.get("currency") or {}
        if not isinstance(before_currency, dict):
            raise CharacterTransferError("currency must be an object")
        for denomination in _DENOMINATIONS:
            old = _strict_nonnegative_int(
                before_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            changed_finals = set()
            for item in items:
                currency = item.plan.post_image.get("currency") or {}
                if not isinstance(currency, dict):
                    raise CharacterTransferError("currency must be an object")
                final = _strict_nonnegative_int(
                    currency.get(denomination, 0),
                    f"currency.{denomination}",
                )
                if final != old:
                    changed_finals.add(final)
            if len(changed_finals) > 1:
                raise CharacterTransferError(
                    f"same-character actions propose conflicting {denomination} finals"
                )
            final = next(iter(changed_finals), old)
            if final != old:
                effective[(path, "currency", denomination)] = final - old

        for family, field, name_field in (
            ("equipment", "equipment", "item_name"),
            ("ammunition", "ammunition", "name"),
        ):
            old_rows = _rows_by_name(before, field, name_field)
            post_rows = [
                _rows_by_name(item.plan.post_image, field, name_field)
                for item in items
            ]
            for name in sorted(
                set(old_rows).union(*(set(rows) for rows in post_rows))
            ):
                old = (
                    _strict_nonnegative_int(
                        old_rows[name].get("quantity", 1),
                        f"{field}.{name}.quantity",
                    )
                    if name in old_rows
                    else 0
                )
                changed_finals = set()
                for rows in post_rows:
                    final = (
                        _strict_nonnegative_int(
                            rows[name].get("quantity", 1),
                            f"{field}.{name}.quantity",
                        )
                        if name in rows
                        else 0
                    )
                    if final != old:
                        changed_finals.add(final)
                if len(changed_finals) > 1:
                    raise CharacterTransferError(
                        f"same-character actions propose conflicting {family} "
                        f"{name} finals"
                    )
                final = next(iter(changed_finals), old)
                if final != old:
                    effective[(path, family, name)] = final - old
    return effective


def _explicit_acquisition_contract_mismatch(
    prepared: Sequence[PreparedCharacterAction],
) -> Optional[str]:
    """Compare explicit positive action facts to the batch's merged finals."""
    try:
        effective = _effective_same_character_asset_deltas(prepared)
    except CharacterTransferError as exc:
        return str(exc)

    stated: Dict[Tuple[str, str, str], int] = {}
    currency_pattern = re.compile(
        rf"\b{_ACQUISITION_VERBS}\s+(\d+)\s+"
        r"(gold|silver|copper)(?:\s+(?:coin|coins|piece|pieces))?\b",
        re.IGNORECASE,
    )
    by_path: Dict[str, List[PreparedCharacterAction]] = {}
    for item in prepared:
        by_path.setdefault(item.plan.canonical_path, []).append(item)
        for amount, denomination in currency_pattern.findall(item.changes):
            key = (item.plan.canonical_path, "currency", denomination.casefold())
            stated[key] = stated.get(key, 0) + int(amount)

    for path, items in by_path.items():
        positive_rows = {
            key: quantity
            for key, quantity in effective.items()
            if key[0] == path and key[1] != "currency" and quantity > 0
        }
        for item in items:
            exact_matched = set()
            for key in positive_rows:
                name = key[2]
                variants = {name}
                if name.endswith("s") and len(name) > 1:
                    variants.add(name[:-1])
                pattern = re.compile(
                    rf"\b{_ACQUISITION_VERBS}\s+(\d+)\s+(?:"
                    + "|".join(
                        re.escape(value)
                        for value in sorted(variants, key=len, reverse=True)
                    )
                    + r")(?=\s|[.,;]|$)",
                    re.IGNORECASE,
                )
                amounts = [int(value) for value in pattern.findall(item.changes)]
                if amounts:
                    stated[key] = stated.get(key, 0) + sum(amounts)
                    exact_matched.add(key)

            # If there is exactly one positive non-currency result, an explicit
            # numbered acquisition sentence can identify it without fuzzy-name
            # matching. Sentences that also state currency stay unclassified;
            # the bounded planner owns those multi-asset shapes in Section D.
            unmatched = [key for key in positive_rows if key not in exact_matched]
            if len(positive_rows) == 1 and len(unmatched) == 1:
                generic = re.compile(
                    rf"\b{_ACQUISITION_VERBS}\s+(\d+)\s+([^.;\n]+)",
                    re.IGNORECASE,
                )
                generic_matches = generic.findall(item.changes)
                if len(generic_matches) == 1 and not currency_pattern.search(
                    item.changes
                ):
                    key = unmatched[0]
                    stated[key] = stated.get(key, 0) + int(generic_matches[0][0])

    for key, expected in sorted(stated.items()):
        actual = effective.get(key, 0)
        if actual != expected:
            _path, family, name = key
            label = name if family != "equipment" else f"{name}"
            return (
                f"stated acquisition of {expected} {label} produced a "
                f"concrete acquisition of {actual} {label}"
            )
    return None


def _validate_transfer_component(
    component: Sequence[PreparedCharacterAction],
) -> Optional[str]:
    paths = [item.plan.canonical_path for item in component]
    if len(paths) != len(set(paths)):
        return "a transfer resolves more than once to the same character"

    grouped: Dict[Tuple[str, str], List[AssetDelta]] = {}
    for item in component:
        for delta in concrete_asset_deltas(item.plan):
            grouped.setdefault(delta.lookup_key, []).append(delta)
    if not any(
        any(value.quantity < 0 for value in values)
        and any(value.quantity > 0 for value in values)
        for values in grouped.values()
    ):
        return "no complementary transfer facts remain"
    for key in sorted(grouped):
        values = grouped[key]
        if not (
            any(value.quantity < 0 for value in values)
            and any(value.quantity > 0 for value in values)
        ):
            return f"{key[0]} {key[1]} is not bidirectional"
        if sum(value.quantity for value in values) != 0:
            return f"{key[0]} {key[1]} is not conserved"
        if key[0] != "currency":
            outgoing = {
                _t052_normalized_metadata(value.metadata)
                for value in values
                if value.quantity < 0
            }
            incoming = {
                _t052_normalized_metadata(value.metadata)
                for value in values
                if value.quantity > 0
            }
            if outgoing != incoming or len(outgoing) != 1:
                return f"{key[0]} {key[1]} has ambiguous mechanical identity"
    return None


def _canonicalize_unambiguous_equipment_transfer(
    component: Sequence[PreparedCharacterAction],
    mismatch: str,
) -> Tuple[Tuple[PreparedCharacterAction, ...], Tuple[str, ...]]:
    """Preserve one transferred item's existing mechanics after model repair.

    The model still chooses the participants, item name, and quantity. This
    seam runs only after the bounded joint correction failed solely because it
    reconstructed the receiver's row with different mechanics.
    """
    if not mismatch.startswith("equipment ") or not mismatch.endswith(
        " has ambiguous mechanical identity"
    ):
        return tuple(component), ()

    equipment_deltas = [
        (item, delta)
        for item in component
        for delta in concrete_asset_deltas(item.plan)
        if delta.family == "equipment"
    ]
    names = {delta.name for _item, delta in equipment_deltas}
    if len(names) != 1:
        return tuple(component), ()
    name = next(iter(names))
    outgoing = [value for value in equipment_deltas if value[1].quantity < 0]
    incoming = [value for value in equipment_deltas if value[1].quantity > 0]
    if len(outgoing) != 1 or len(incoming) != 1:
        return tuple(component), ()
    giver, removed = outgoing[0]
    receiver, added = incoming[0]
    if -removed.quantity != added.quantity:
        return tuple(component), ()

    source_rows = [
        row
        for row in giver.plan.pre_image.get("equipment", []) or []
        if isinstance(row, dict)
        and _normalized_name(row.get("item_name")) == name
    ]
    if len(source_rows) != 1:
        return tuple(component), ()
    receiver_before_rows = receiver.plan.pre_image.get("equipment", []) or []
    receiver_after_rows = receiver.plan.post_image.get("equipment", []) or []
    if not isinstance(receiver_before_rows, list) or not isinstance(
        receiver_after_rows, list
    ):
        return tuple(component), ()
    before_named = [
        copy.deepcopy(row)
        for row in receiver_before_rows
        if isinstance(row, dict)
        and _normalized_name(row.get("item_name")) == name
    ]
    after_named = [
        row
        for row in receiver_after_rows
        if isinstance(row, dict)
        and _normalized_name(row.get("item_name")) == name
    ]
    if len(before_named) > 1 or len(after_named) != 1:
        return tuple(component), ()

    canonical = copy.deepcopy(source_rows[0])
    canonical["quantity"] = added.quantity
    canonical["equipped"] = False
    replacement_rows, _identity_advisories = consolidate_equipment_rows(
        before_named + [canonical]
    )
    # Existing same-named non-identical or unique rows remain distinct under
    # the shared L2 rules. Do not force them together to make this transfer fit.
    if len(replacement_rows) != 1:
        return tuple(component), ()

    post_image = copy.deepcopy(receiver.plan.post_image)
    replaced = False
    rebuilt = []
    for row in receiver_after_rows:
        if (
            isinstance(row, dict)
            and _normalized_name(row.get("item_name")) == name
        ):
            if not replaced:
                rebuilt.extend(copy.deepcopy(replacement_rows))
                replaced = True
            continue
        rebuilt.append(copy.deepcopy(row))
    post_image["equipment"] = rebuilt
    advisory = f"transfer_metadata_canonicalized:{name}"
    updated_plan = replace(
        receiver.plan,
        post_image=post_image,
        field_facts=tuple(_field_change_facts(receiver.plan.pre_image, post_image)),
        advisories=tuple(sorted(set(receiver.plan.advisories + (advisory,)))),
    )
    updated_receiver = replace(receiver, plan=updated_plan)
    updated_component = tuple(
        updated_receiver if item.index == receiver.index else item
        for item in component
    )
    warning(f"INVENTORY: {advisory}", category="character_updates")
    return updated_component, (advisory,)


def _action_changes(action: Mapping[str, Any]) -> str:
    parameters = action.get("parameters") or {}
    changes = parameters.get("changes")
    if not changes or not isinstance(changes, (str, dict)):
        raise CharacterTransferError("updateCharacterInfo requires useful changes")
    return changes if isinstance(changes, str) else json.dumps(changes)


def _action_character(action: Mapping[str, Any], party: Mapping[str, Any]) -> str:
    parameters = action.get("parameters") or {}
    name = parameters.get("characterName") or parameters.get("npcName")
    if not name:
        name = next(iter(party.get("partyMembers") or []), None)
    if not name:
        raise CharacterTransferError("updateCharacterInfo has no character")
    return str(name)


def _prepare_actions(
    indexed_actions: Sequence[Tuple[int, Mapping[str, Any]]],
    party: Mapping[str, Any],
    correction: Optional[str] = None,
) -> Tuple[PreparedCharacterAction, ...]:
    prepared = []
    for index, action in indexed_actions:
        changes = _action_changes(action)
        request = changes
        if correction:
            request = (
                f"{changes}\n\nJOINT TRANSFER CORRECTION (one final attempt): "
                f"{correction}. Return the exact final values needed so every "
                "transferred item, ammunition unit, and copper-equivalent coin "
                "removed from one named character is added to another. Preserve "
                "the item's complete mechanical metadata."
            )
        plan = prepare_character_with_effects(
            _action_character(action, party),
            request,
            party,
        )
        if not isinstance(plan, CharacterMutationPlan):
            raise CharacterTransferError(
                f"character update preparation failed at action {index}"
            )
        prepared.append(PreparedCharacterAction(index, action, changes, plan))
    return tuple(prepared)


def process_character_update_batch(
    indexed_actions: Sequence[Tuple[int, Mapping[str, Any]]],
    party_tracker_data: Mapping[str, Any],
) -> Dict[str, Any]:
    """Prepare original indexed actions and atomically commit transfer components."""
    try:
        prepared = _prepare_actions(indexed_actions, party_tracker_data)
        return commit_prepared_character_actions(prepared, party_tracker_data)
    except Exception as exc:
        return _character_batch_failure(
            exc,
            stage="character_prepare",
            action_indices=(index for index, _action in indexed_actions),
        )


def prepare_character_actions(
    indexed_actions: Sequence[Tuple[int, Mapping[str, Any]]],
    party_tracker_data: Mapping[str, Any],
) -> Tuple[PreparedCharacterAction, ...]:
    """Public preparation seam used by adjacent atomic adapters."""
    return _prepare_actions(indexed_actions, party_tracker_data)


def _character_batch_failure(
    exc: Exception,
    *,
    stage: str = "character_batch",
    action_indices=(),
) -> Dict[str, Any]:
    indices = sorted(
        {
            value
            for value in action_indices
            if type(value) is int and 0 <= value <= 4096
        }
    )
    return {
        "status": "error",
        "success": False,
        "response_data": {
            "error_message": (
                "The character transfer or inventory update could not be "
                "verified, so no unsafe partial transfer was applied."
            ),
            "failure_code": "character_transfer_unverified",
        },
        "diagnostic": str(exc),
        "exception_class": type(exc).__name__,
        "failed_stage": stage,
        "action_indices": indices,
    }


def commit_prepared_character_actions(
    prepared: Sequence[PreparedCharacterAction],
    party_tracker_data: Mapping[str, Any],
    *,
    prepare_only: bool = False,
    resource_storage_plans=(),
    enable_resource_planning: bool = False,
) -> Dict[str, Any]:
    """Validate a prepared subset and optionally commit it.

    ``prepare_only`` exposes the fully corrected, graph-validated images to the
    response-level resource transaction without weakening the established
    transfer checks or performing an early write.
    """
    failed_stage = "character_batch_input"
    action_indices = ()
    try:
        prepared = tuple(prepared)
        action_indices = tuple(item.index for item in prepared)
        shape_corrected_indices = set()
        failed_stage = "explicit_stated_value_contract"
        stated_value_mismatch = _explicit_removal_contract_mismatch(prepared)
        if not stated_value_mismatch:
            stated_value_mismatch = _explicit_acquisition_contract_mismatch(
                prepared
            )
        if stated_value_mismatch:
            correction = (
                f"{stated_value_mismatch}. Explicit numbered resource changes "
                "must produce that exact concrete increase or decrease; never "
                "duplicate, clamp, floor, partially apply, or substitute "
                "another resource"
            )
            corrected = _prepare_actions(
                tuple((item.index, item.action) for item in prepared),
                party_tracker_data,
                correction=correction,
            )
            remaining_stated_value_mismatch = _explicit_removal_contract_mismatch(
                corrected
            )
            if not remaining_stated_value_mismatch:
                remaining_stated_value_mismatch = (
                    _explicit_acquisition_contract_mismatch(corrected)
                )
            if remaining_stated_value_mismatch:
                raise CharacterTransferError(
                    "explicit stated-value correction failed safely: "
                    f"{remaining_stated_value_mismatch}"
                )
            prepared = corrected
            shape_corrected_indices = {item.index for item in prepared}
        planning_result = None
        if enable_resource_planning:
            failed_stage = "resource_transaction_planning"
            import model_config
            from core.managers.resource_transaction_planning import (
                plan_and_stage_resource_transaction,
            )

            planning_result = plan_and_stage_resource_transaction(
                prepared,
                tuple(resource_storage_plans),
                provider=model_config.get_provider(),
            )
            prepared = planning_result.character_actions
            resource_storage_plans = planning_result.storage_plans
        failed_stage = "transfer_shape_validation"
        shape_mismatch = _batch_transfer_shape_mismatch(prepared)
        if shape_mismatch:
            if shape_corrected_indices:
                raise CharacterTransferError(
                    f"transfer correction failed safely: {shape_mismatch}"
                )
            correction = _correction_with_canonical_source_names(
                shape_mismatch,
                prepared,
            )
            corrected = _prepare_actions(
                tuple((item.index, item.action) for item in prepared),
                party_tracker_data,
                correction=correction,
            )
            remaining_shape_mismatch = _batch_transfer_shape_mismatch(corrected)
            if remaining_shape_mismatch:
                raise CharacterTransferError(
                    "transfer correction failed safely: "
                    f"{remaining_shape_mismatch}"
                )
            prepared = corrected
            shape_corrected_indices = {item.index for item in prepared}
        by_index = {item.index: item for item in prepared}
        components = _candidate_components(prepared)

        corrected_components = {}
        failed_stage = "transfer_component_validation"
        for indices in components:
            component = tuple(by_index[index] for index in indices)
            mismatch = _validate_transfer_component(component)
            if mismatch:
                if set(indices).issubset(shape_corrected_indices):
                    corrected = component
                else:
                    correction = _correction_with_canonical_source_names(
                        mismatch,
                        component,
                    )
                    corrected = _prepare_actions(
                        tuple((item.index, item.action) for item in component),
                        party_tracker_data,
                        correction=correction,
                    )
                    mismatch = _validate_transfer_component(corrected)
                if mismatch:
                    corrected, _canonicalization_advisories = (
                        _canonicalize_unambiguous_equipment_transfer(
                            corrected,
                            mismatch,
                        )
                    )
                    mismatch = _validate_transfer_component(corrected)
                    if mismatch:
                        raise CharacterTransferError(
                            f"transfer correction failed safely: {mismatch}"
                        )
                corrected_components[indices] = corrected

        units = []
        claimed = set()
        for indices in components:
            component = corrected_components.get(
                indices,
                tuple(by_index[index] for index in indices),
            )
            units.append((min(indices), component, "character_transfer"))
            claimed.update(indices)
        for item in prepared:
            if item.index not in claimed:
                units.append((item.index, (item,), "character_update"))

        prepared_actions = tuple(
            item
            for _index, unit, _operation in sorted(
                units, key=lambda value: value[0]
            )
            for item in unit
        )
        if prepare_only:
            return {
                "status": "continue",
                "success": True,
                "needs_update": bool(prepared_actions),
                "prepared_actions": prepared_actions,
                "prepared_indices": [item.index for item in prepared_actions],
                "storage_plans": tuple(resource_storage_plans),
                "resource_planning": planning_result,
            }

        from utils.state_transaction import TransactionStalePlanError

        failed_stage = "character_commit"
        for _index, unit, operation in sorted(units, key=lambda value: value[0]):
            try:
                execute_character_mutation_plans(
                    tuple(item.plan for item in unit),
                    operation=operation,
                )
            except TransactionStalePlanError:
                # Leases are already released by the coordinator. Re-run all
                # model preparation once against the new snapshots, then
                # revalidate the concrete component before the final attempt.
                failed_stage = "character_stale_reprepare"
                refreshed = _prepare_actions(
                    tuple((item.index, item.action) for item in unit),
                    party_tracker_data,
                )
                if operation == "character_transfer":
                    mismatch = _validate_transfer_component(refreshed)
                    if mismatch:
                        indices = tuple(sorted(item.index for item in unit))
                        if indices in corrected_components:
                            raise CharacterTransferError(
                                "stale transfer still violates conservation"
                            )
                        correction = _correction_with_canonical_source_names(
                            mismatch,
                            refreshed,
                        )
                        refreshed = _prepare_actions(
                            tuple((item.index, item.action) for item in unit),
                            party_tracker_data,
                            correction=correction,
                        )
                        if _validate_transfer_component(refreshed):
                            raise CharacterTransferError(
                                "stale transfer correction failed safely"
                            )
                execute_character_mutation_plans(
                    tuple(item.plan for item in refreshed),
                    operation=operation,
                )
                failed_stage = "character_commit"

        rest_kinds = {
            (
                "long_rest"
                if "long rest" in item.changes.casefold()
                else "short_rest" if "short rest" in item.changes.casefold() else None
            )
            for item in prepared
        }
        for rest_kind in sorted(value for value in rest_kinds if value):
            from core.managers.effects_runtime import process_effect_lifecycle

            failed_stage = "effect_lifecycle"
            process_effect_lifecycle(rest_kind=rest_kind)
        return {
            "status": "continue",
            "success": True,
            "needs_update": bool(prepared),
            "committed_indices": [item.index for item in prepared],
        }
    except Exception as exc:
        return _character_batch_failure(
            exc,
            stage=failed_stage,
            action_indices=action_indices,
        )


def prepare_character_response_actions(
    prepared: Sequence[PreparedCharacterAction],
    party_tracker_data: Mapping[str, Any],
    storage_plans=(),
) -> Dict[str, Any]:
    """Return transfer-validated response images without changing files."""
    return commit_prepared_character_actions(
        prepared,
        party_tracker_data,
        prepare_only=True,
        resource_storage_plans=tuple(storage_plans),
        enable_resource_planning=True,
    )


def process_character_response_effects(
    prepared: Sequence[PreparedCharacterAction],
) -> None:
    """Advance rest-linked effects only after the resource commit succeeds."""
    rest_kinds = {
        (
            "long_rest"
            if "long rest" in item.changes.casefold()
            else "short_rest" if "short rest" in item.changes.casefold() else None
        )
        for item in prepared
    }
    for rest_kind in sorted(value for value in rest_kinds if value):
        from core.managers.effects_runtime import process_effect_lifecycle

        process_effect_lifecycle(rest_kind=rest_kind)
