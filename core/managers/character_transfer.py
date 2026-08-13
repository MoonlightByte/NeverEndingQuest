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


_RESOURCE_TOKEN_STOPWORDS = {
    "a",
    "an",
    "and",
    "from",
    "in",
    "into",
    "of",
    "the",
    "to",
}

_PARTY_NAME_ROLE_TOKENS = {
    "captain",
    "commander",
    "merchant",
    "messenger",
    "quartermaster",
    "ranger",
    "scout",
}


@dataclass(frozen=True)
class _PartyAttributedRequirement:
    claimant_index: int
    target_name: str
    family: str
    name: str
    quantity: int


def _party_character_names(party: Mapping[str, Any]) -> Tuple[str, ...]:
    names = []
    for value in party.get("partyMembers") or []:
        if isinstance(value, str) and value.strip():
            names.append(value.strip())
    for value in party.get("partyNPCs") or []:
        if isinstance(value, Mapping):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return tuple(dict.fromkeys(names))


def _party_name_aliases(party: Mapping[str, Any]) -> Dict[str, Tuple[str, ...]]:
    """Return full names plus unambiguous non-role name tokens."""
    names = _party_character_names(party)
    token_owners: Dict[str, set] = {}
    name_tokens = {}
    for name in names:
        tokens = tuple(re.findall(r"[a-z0-9]+", name.casefold()))
        name_tokens[name] = tokens
        for token in tokens:
            if len(token) < 3 or token in _PARTY_NAME_ROLE_TOKENS:
                continue
            token_owners.setdefault(token, set()).add(name)
    result = {}
    for name in names:
        aliases = {" ".join(name_tokens[name])}
        aliases.update(
            token
            for token in name_tokens[name]
            if len(token) >= 3
            and token not in _PARTY_NAME_ROLE_TOKENS
            and token_owners.get(token) == {name}
        )
        result[name] = tuple(sorted(aliases, key=lambda value: (-len(value), value)))
    return result


def _attributed_party_names(
    changes: str,
    marker: str,
    actor_name: str,
    party: Mapping[str, Any],
) -> Tuple[str, ...]:
    text = changes.casefold()
    actor_key = _normalized_name(actor_name)
    matches = []
    for name, aliases in _party_name_aliases(party).items():
        if _normalized_name(name) == actor_key:
            continue
        if any(
            re.search(
                rf"\b{re.escape(marker)}\s+(?:the\s+)?{re.escape(alias)}\b",
                text,
            )
            for alias in aliases
        ):
            matches.append(name)
    return tuple(dict.fromkeys(matches))


def _denomination_deltas(item: PreparedCharacterAction) -> Dict[str, int]:
    before = item.plan.pre_image.get("currency") or {}
    after = item.plan.post_image.get("currency") or {}
    return {
        denomination: _strict_nonnegative_int(
            after.get(denomination, 0), f"currency.{denomination}"
        )
        - _strict_nonnegative_int(
            before.get(denomination, 0), f"currency.{denomination}"
        )
        for denomination in sorted(_DENOMINATIONS)
    }


def _party_attributed_requirements(
    prepared: Sequence[PreparedCharacterAction],
    party: Mapping[str, Any],
) -> Tuple[_PartyAttributedRequirement, ...]:
    requirements = []
    for item in prepared:
        incoming_names = _attributed_party_names(
            item.changes, "from", item.plan.character_name, party
        )
        outgoing_names = _attributed_party_names(
            item.changes, "to", item.plan.character_name, party
        )
        resource_deltas = list(concrete_asset_deltas(item.plan))
        resource_deltas.extend(
            AssetDelta("currency", denomination, quantity, "currency")
            for denomination, quantity in _denomination_deltas(item).items()
            if quantity
        )
        for delta in resource_deltas:
            if delta.family == "currency" and delta.name == "currency":
                continue
            if not _changes_mention_resource(
                item.changes, delta.family, delta.name
            ):
                continue
            if delta.quantity > 0:
                for source_name in incoming_names:
                    requirements.append(
                        _PartyAttributedRequirement(
                            item.index,
                            source_name,
                            delta.family,
                            delta.name,
                            -delta.quantity,
                        )
                    )
            elif delta.quantity < 0:
                for recipient_name in outgoing_names:
                    requirements.append(
                        _PartyAttributedRequirement(
                            item.index,
                            recipient_name,
                            delta.family,
                            delta.name,
                            -delta.quantity,
                        )
                    )
    return tuple(dict.fromkeys(requirements))


def _actor_resource_delta(
    prepared: Sequence[PreparedCharacterAction],
    actor_name: str,
    family: str,
    name: str,
) -> Optional[int]:
    values = set()
    actor_key = _normalized_name(actor_name)
    for item in prepared:
        if _normalized_name(item.plan.character_name) != actor_key:
            continue
        if family == "currency":
            quantity = _denomination_deltas(item).get(name, 0)
            if quantity:
                values.add(quantity)
            continue
        for delta in concrete_asset_deltas(item.plan):
            if delta.family == family and delta.name == name and delta.quantity:
                values.add(delta.quantity)
    if not values:
        return 0
    if len(values) == 1:
        return next(iter(values))
    return None


def _missing_party_attributed_requirements(
    prepared: Sequence[PreparedCharacterAction],
    party: Mapping[str, Any],
) -> Tuple[_PartyAttributedRequirement, ...]:
    return tuple(
        requirement
        for requirement in _party_attributed_requirements(prepared, party)
        if _actor_resource_delta(
            prepared,
            requirement.target_name,
            requirement.family,
            requirement.name,
        )
        != requirement.quantity
    )


def _party_attributed_correction_fact(
    requirement: _PartyAttributedRequirement,
    prepared: Sequence[PreparedCharacterAction],
    party: Mapping[str, Any],
) -> str:
    target = next(
        (
            item
            for item in prepared
            if _normalized_name(item.plan.character_name)
            == _normalized_name(requirement.target_name)
        ),
        None,
    )
    pre_image = (
        target.plan.pre_image
        if target is not None
        else _party_character_snapshot(requirement.target_name, party)
    )
    if requirement.family == "currency":
        current = _strict_nonnegative_int(
            (pre_image.get("currency") or {}).get(requirement.name, 0),
            f"currency.{requirement.name}",
        )
        label = f"currency {requirement.name}"
    else:
        current = _row_quantity_for_name(
            pre_image,
            requirement.family,
            requirement.name,
        )
        label = f"{requirement.family} {requirement.name}"
    final = current + requirement.quantity
    if final < 0:
        raise CharacterTransferError(
            f"party-attributed {label} transfer would overdraw {requirement.target_name}"
        )
    return (
        f"{label}: current {current}, required signed delta "
        f"{requirement.quantity:+d}, required final {final}"
    )


def _party_character_snapshot(
    character_name: str,
    party: Mapping[str, Any],
) -> Mapping[str, Any]:
    from updates.update_character_info import get_character_path
    from utils.encoding_utils import safe_json_load

    role = (
        "player"
        if any(
            _normalized_name(value) == _normalized_name(character_name)
            for value in party.get("partyMembers") or []
        )
        else "npc"
    )
    sheet = safe_json_load(get_character_path(character_name, role))
    if not isinstance(sheet, dict):
        raise CharacterTransferError(
            "party-attributed counterpart character sheet is unavailable"
        )
    return sheet


def _synthesize_negative_party_counterparts(
    original: Sequence[PreparedCharacterAction],
    corrected: Sequence[PreparedCharacterAction],
    original_missing: Sequence[_PartyAttributedRequirement],
    remaining: Sequence[_PartyAttributedRequirement],
    target_indices: Mapping[str, int],
) -> Tuple[PreparedCharacterAction, ...]:
    """Apply only exact removal mirrors after the model correction fails.

    The accepted positive sibling and party attribution already prove the
    actor, resource identity, and quantity.  Code may therefore enforce the
    missing negative half as conservation arithmetic.  Additions and any
    competing or ambiguous actor state remain model-owned and fail closed.
    """
    failing_targets = {value.target_name for value in remaining}
    requirements_by_target: Dict[str, List[_PartyAttributedRequirement]] = {}
    for requirement in original_missing:
        if requirement.target_name in failing_targets:
            requirements_by_target.setdefault(
                requirement.target_name, []
            ).append(requirement)

    original_by_index = {item.index: item for item in original}
    corrected_by_index = {item.index: item for item in corrected}
    replacements = {}
    for target_name, requirements in requirements_by_target.items():
        if not requirements or any(value.quantity >= 0 for value in requirements):
            continue
        target_index = target_indices.get(target_name)
        if target_index is None:
            continue
        base = original_by_index.get(target_index)
        corrected_item = corrected_by_index.get(target_index)
        if base is None:
            base = corrected_item
            if base is None:
                continue
            post_image = copy.deepcopy(base.plan.pre_image)
        else:
            post_image = copy.deepcopy(base.plan.post_image)

        eligible = True
        advisories = set(base.plan.advisories)
        for requirement in requirements:
            if _actor_resource_delta(
                original,
                target_name,
                requirement.family,
                requirement.name,
            ) != 0:
                eligible = False
                break
            if requirement.family == "currency":
                before_currency = base.plan.pre_image.get("currency") or {}
                after_currency = post_image.get("currency") or {}
                if not isinstance(before_currency, dict) or not isinstance(
                    after_currency, dict
                ):
                    eligible = False
                    break
                current = _strict_nonnegative_int(
                    before_currency.get(requirement.name, 0),
                    f"currency.{requirement.name}",
                )
                if _strict_nonnegative_int(
                    after_currency.get(requirement.name, 0),
                    f"currency.{requirement.name}",
                ) != current:
                    eligible = False
                    break
                final = current + requirement.quantity
                if final < 0:
                    eligible = False
                    break
                after_currency = copy.deepcopy(after_currency)
                after_currency[requirement.name] = final
                post_image["currency"] = after_currency
            elif requirement.family in {"equipment", "ammunition"}:
                field, name_field = (
                    ("equipment", "item_name")
                    if requirement.family == "equipment"
                    else ("ammunition", "name")
                )
                before_rows = base.plan.pre_image.get(field) or []
                after_rows = post_image.get(field) or []
                if not isinstance(before_rows, list) or not isinstance(
                    after_rows, list
                ):
                    eligible = False
                    break
                before_matches = [
                    row
                    for row in before_rows
                    if isinstance(row, dict)
                    and _normalized_name(row.get(name_field))
                    == requirement.name
                ]
                after_matches = [
                    row
                    for row in after_rows
                    if isinstance(row, dict)
                    and _normalized_name(row.get(name_field))
                    == requirement.name
                ]
                if len(before_matches) != 1 or len(after_matches) != 1:
                    eligible = False
                    break
                source = before_matches[0]
                candidate = after_matches[0]
                current = _strict_nonnegative_int(
                    source.get("quantity", 1),
                    f"{field}.{requirement.name}.quantity",
                )
                if (
                    _strict_nonnegative_int(
                        candidate.get("quantity", 1),
                        f"{field}.{requirement.name}.quantity",
                    )
                    != current
                    or inventory_metadata(source, name_field)
                    != inventory_metadata(candidate, name_field)
                ):
                    eligible = False
                    break
                final = current + requirement.quantity
                if final < 0:
                    eligible = False
                    break
                rebuilt = []
                for row in after_rows:
                    if row is candidate:
                        if final:
                            canonical = copy.deepcopy(source)
                            canonical["quantity"] = final
                            rebuilt.append(canonical)
                        continue
                    rebuilt.append(copy.deepcopy(row))
                post_image[field] = rebuilt
            else:
                eligible = False
                break
            advisories.add(
                "conservation_counterpart_synthesized:%s:%s"
                % (requirement.family, requirement.name)
            )
        if not eligible:
            continue

        plan = replace(
            base.plan,
            post_image=post_image,
            field_facts=tuple(
                _field_change_facts(base.plan.pre_image, post_image)
            ),
            advisories=tuple(sorted(advisories)),
        )
        replacements[target_index] = replace(base, plan=plan)

    return tuple(replacements.get(item.index, item) for item in corrected)


def _repair_party_attributed_requirements(
    prepared: Sequence[PreparedCharacterAction],
    party: Mapping[str, Any],
) -> Tuple[PreparedCharacterAction, ...]:
    missing = _missing_party_attributed_requirements(prepared, party)
    if not missing:
        return tuple(prepared)

    prepared = tuple(prepared)
    by_target: Dict[str, List[_PartyAttributedRequirement]] = {}
    for requirement in missing:
        by_target.setdefault(requirement.target_name, []).append(requirement)

    selected_actions = {}
    corrections = {}
    target_indices = {}
    next_index = max((item.index for item in prepared), default=-1) + 1
    for target_name, requirements in by_target.items():
        candidates = [
            item
            for item in prepared
            if _normalized_name(item.plan.character_name)
            == _normalized_name(target_name)
        ]
        if candidates:
            resource_matched = [
                item
                for item in candidates
                if any(
                    _changes_mention_resource(
                        item.changes, requirement.family, requirement.name
                    )
                    for requirement in requirements
                )
            ]
            target = min(resource_matched or candidates, key=lambda item: item.index)
            target_index = target.index
            target_action = target.action
        else:
            target_index = next_index
            next_index += 1
            target_action = {
                "action": "updateCharacterInfo",
                "parameters": {
                    "characterName": target_name,
                    "changes": (
                        "Apply the mandatory party-attributed transfer counterpart."
                    ),
                },
            }
        facts = "; ".join(
            _party_attributed_correction_fact(requirement, prepared, party)
            for requirement in requirements
        )
        selected_actions[target_index] = target_action
        target_indices[target_name] = target_index
        corrections[target_index] = (
            f"Party-attributed transfer facts for {target_name} only: {facts}. "
            "The accepted sibling action explicitly attributes this resource "
            "movement to this current party member, so its exact opposite half "
            "is mandatory. Preserve every unrelated field exactly"
        )

    corrected = _prepare_actions(
        tuple(sorted(selected_actions.items())),
        party,
        correction=corrections,
    )
    replacements = {item.index: item for item in corrected}
    existing_indices = {item.index for item in prepared}
    result = tuple(replacements.get(item.index, item) for item in prepared) + tuple(
        item
        for item in corrected
        if item.index not in existing_indices
    )
    remaining = _missing_party_attributed_requirements(result, party)
    if remaining:
        result = _synthesize_negative_party_counterparts(
            prepared,
            result,
            missing,
            remaining,
            target_indices,
        )
        remaining = _missing_party_attributed_requirements(result, party)
    if remaining:
        labels = ", ".join(
            f"{value.target_name} {value.family} {value.name} "
            f"{value.quantity:+d}"
            for value in remaining
        )
        raise CharacterTransferError(
            "party-attributed transfer correction failed safely: " + labels
        )
    return result


_PARTY_CURRENCY_AGGREGATE_ADVISORY = (
    "party_currency_aggregate_changed_without_external_action"
)


def _with_party_currency_aggregate_advisory(
    prepared: Sequence[PreparedCharacterAction],
    party: Mapping[str, Any],
) -> Tuple[PreparedCharacterAction, ...]:
    """Flag party-only currency creation/destruction without blocking play."""
    prepared = tuple(prepared)
    roster = {_normalized_name(name) for name in _party_character_names(party)}
    if not prepared or not roster or any(
        _normalized_name(item.plan.character_name) not in roster for item in prepared
    ):
        return prepared

    by_path: Dict[Tuple[str, str], set] = {}
    for item in prepared:
        for denomination, quantity in _denomination_deltas(item).items():
            if quantity:
                by_path.setdefault(
                    (item.plan.canonical_path, denomination), set()
                ).add(quantity)
    if any(len(values) != 1 for values in by_path.values()):
        return prepared
    aggregate = sum(
        next(iter(values)) * _DENOMINATIONS[denomination]
        for (_path, denomination), values in by_path.items()
    )
    if not aggregate:
        return prepared

    changed = []
    applied = False
    for item in prepared:
        if not applied and any(_denomination_deltas(item).values()):
            advisory_values = tuple(
                sorted(
                    set(
                        item.plan.advisories
                        + (_PARTY_CURRENCY_AGGREGATE_ADVISORY,)
                    )
                )
            )
            item = replace(item, plan=replace(item.plan, advisories=advisory_values))
            applied = True
        changed.append(item)
    warning(
        "INVENTORY: " + _PARTY_CURRENCY_AGGREGATE_ADVISORY,
        category="character_updates",
    )
    return tuple(changed)


def _resource_tokens(value: Any) -> set:
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", str(value).casefold()):
        if len(token) < 3 or token in _RESOURCE_TOKEN_STOPWORDS:
            continue
        tokens.add(token)
        if len(token) > 3 and token.endswith("s"):
            tokens.add(token[:-1])
    return tokens


def _changes_mention_resource(
    changes: str,
    family: str,
    name: str,
) -> bool:
    text = changes.casefold()
    if family == "currency":
        return name.casefold() in text
    return bool(_resource_tokens(name) & _resource_tokens(text))


def _exact_delta_row(
    item: PreparedCharacterAction,
    delta: AssetDelta,
) -> Optional[Mapping[str, Any]]:
    if delta.family not in {"equipment", "ammunition"}:
        return None
    field, name_field = (
        ("equipment", "item_name")
        if delta.family == "equipment"
        else ("ammunition", "name")
    )
    image = item.plan.pre_image if delta.quantity < 0 else item.plan.post_image
    matches = [
        row
        for row in image.get(field) or []
        if isinstance(row, dict)
        and _normalized_name(row.get(name_field)) == delta.name
    ]
    return matches[0] if len(matches) == 1 else None


def _row_quantity_for_name(
    image: Mapping[str, Any],
    family: str,
    name: str,
) -> int:
    field, name_field = (
        ("equipment", "item_name")
        if family == "equipment"
        else ("ammunition", "name")
    )
    matches = [
        row
        for row in image.get(field) or []
        if isinstance(row, dict)
        and _normalized_name(row.get(name_field)) == _normalized_name(name)
    ]
    if not matches:
        return 0
    if len(matches) != 1:
        raise CharacterTransferError(
            f"{field}.{_normalized_name(name)} has ambiguous rows"
        )
    return _strict_nonnegative_int(
        matches[0].get("quantity", 1),
        f"{field}.{_normalized_name(name)}.quantity",
    )


def _participant_scoped_corrections(
    prepared: Sequence[PreparedCharacterAction],
) -> Dict[int, str]:
    """Build actor-local correction facts without broadcasting other finals."""
    prepared = tuple(prepared)
    relevant_deltas = {}
    for item in prepared:
        relevant_deltas[item.index] = tuple(
            delta
            for delta in concrete_asset_deltas(item.plan)
            if delta.family != "currency"
            and _changes_mention_resource(
                item.changes,
                delta.family,
                delta.name,
            )
        )

    inferred_incoming = {item.index: [] for item in prepared}
    for source in prepared:
        for source_delta in relevant_deltas[source.index]:
            if source_delta.quantity >= 0:
                continue
            source_row = _exact_delta_row(source, source_delta)
            if source_row is None:
                continue
            candidates = []
            for receiver in prepared:
                if receiver.index == source.index or (
                    receiver.plan.canonical_path == source.plan.canonical_path
                ):
                    continue
                if not _changes_mention_resource(
                    receiver.changes,
                    source_delta.family,
                    source_delta.name,
                ):
                    continue
                if any(
                    delta.quantity > 0
                    and delta.family == source_delta.family
                    and _changes_mention_resource(
                        receiver.changes,
                        delta.family,
                        delta.name,
                    )
                    for delta in relevant_deltas[receiver.index]
                ):
                    continue
                candidates.append(receiver)
            if len(candidates) == 1:
                inferred_incoming[candidates[0].index].append(
                    (source_delta, source_row)
                )

    corrections = {}
    for item in prepared:
        character_name = item.plan.character_name
        facts = []
        before_currency = item.plan.pre_image.get("currency") or {}
        after_currency = item.plan.post_image.get("currency") or {}
        for denomination in sorted(_DENOMINATIONS):
            before = _strict_nonnegative_int(
                before_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            after = _strict_nonnegative_int(
                after_currency.get(denomination, 0),
                f"currency.{denomination}",
            )
            delta = after - before
            if not delta or not _changes_mention_resource(
                item.changes,
                "currency",
                denomination,
            ):
                continue
            facts.append(
                f"currency {denomination}: current {before}, required signed "
                f"delta {delta:+d}, required final {after}"
            )

        for delta in relevant_deltas[item.index]:
            canonical_name = delta.name
            canonical_row = _exact_delta_row(item, delta)
            if delta.quantity > 0:
                candidates = []
                for other in prepared:
                    if other.index == item.index or (
                        other.plan.canonical_path == item.plan.canonical_path
                    ):
                        continue
                    for other_delta in relevant_deltas[other.index]:
                        if (
                            other_delta.family == delta.family
                            and other_delta.quantity == -delta.quantity
                            and _changes_mention_resource(
                                item.changes,
                                other_delta.family,
                                other_delta.name,
                            )
                        ):
                            row = _exact_delta_row(other, other_delta)
                            if row is not None:
                                candidates.append((other_delta, row))
                if len(candidates) == 1:
                    source_delta, canonical_row = candidates[0]
                    canonical_name = source_delta.name

            field_name = "item_name" if delta.family == "equipment" else "name"
            exact_name = (
                canonical_row.get(field_name)
                if isinstance(canonical_row, Mapping)
                else canonical_name
            )
            current = _row_quantity_for_name(
                item.plan.pre_image,
                delta.family,
                str(exact_name),
            )
            final = current + delta.quantity
            facts.append(
                f"{delta.family} {field_name}="
                f"{json.dumps(exact_name, ensure_ascii=False)}: current "
                f"{current}, required signed delta {delta.quantity:+d}, "
                f"required final {final}; must reuse this exact canonical name"
            )

        for source_delta, source_row in inferred_incoming[item.index]:
            field_name = (
                "item_name" if source_delta.family == "equipment" else "name"
            )
            exact_name = source_row.get(field_name)
            current = _row_quantity_for_name(
                item.plan.pre_image,
                source_delta.family,
                str(exact_name),
            )
            amount = -source_delta.quantity
            facts.append(
                f"{source_delta.family} {field_name}="
                f"{json.dumps(exact_name, ensure_ascii=False)}: current "
                f"{current}, required signed delta {amount:+d}, required final "
                f"{current + amount}; must reuse this exact canonical name"
            )

        fact_text = "; ".join(facts) if facts else "no resource-field change"
        corrections[item.index] = (
            f"Canonical facts for {character_name} only: {fact_text}. Apply only the "
            "resource movements stated in this actor's accepted changes. "
            "Preserve every unrelated resource field and row exactly; do not "
            "copy another participant's balances, rows, or absolute finals"
        )
    return corrections


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
_NON_QUANTITY_UNIT_WORDS = frozenset(
    {
        "centimeter",
        "centimeters",
        "day",
        "days",
        "feet",
        "foot",
        "ft",
        "gallon",
        "gallons",
        "hour",
        "hours",
        "inch",
        "inches",
        "lb",
        "lbs",
        "liter",
        "liters",
        "meter",
        "meters",
        "mile",
        "miles",
        "minute",
        "minutes",
        "ounce",
        "ounces",
        "pound",
        "pounds",
        "yard",
        "yards",
    }
)
_COMMERCE_DISPOSAL_VERBS = r"(?:removed|sold|gave|handed|traded|transferred)"
_COMMERCE_GENERIC_TOKENS = {
    "armor",
    "charge",
    "charges",
    "equipment",
    "experience",
    "gear",
    "hp",
    "inventory",
    "item",
    "items",
    "level",
    "levels",
    "new",
    "points",
    "slot",
    "slots",
    "use",
    "uses",
    "weapon",
    "xp",
}
_AMMUNITION_TOKENS = {
    "arrow",
    "arrows",
    "bolt",
    "bolts",
    "bullet",
    "bullets",
    "shot",
}


def _commerce_item_statements(text: str):
    verbs = rf"(?P<verb>{_ACQUISITION_VERBS}|{_COMMERCE_DISPOSAL_VERBS})"
    other_statement = (
        rf"\s+and\s+(?:{_ACQUISITION_VERBS}|{_COMMERCE_DISPOSAL_VERBS})"
        r"\s+\d+\s+(?:gold|silver|copper)\b"
    )
    pattern = re.compile(
        rf"\b{verbs}\s+(?P<quantity>\d+)\s+(?P<descriptor>.+?)"
        rf"(?={other_statement}|[.;\n]|$)",
        re.IGNORECASE,
    )
    statements = []
    for match in pattern.finditer(text):
        descriptor = match.group("descriptor").strip(" ,")
        descriptor = re.sub(
            r"\s+(?:to|from|into)\s+(?:the\s+)?inventory$",
            "",
            descriptor,
            flags=re.IGNORECASE,
        ).strip(" ,")
        tokens = _resource_tokens(descriptor) - _COMMERCE_GENERIC_TOKENS
        if not descriptor or not tokens or tokens <= {
            "gold",
            "silver",
            "copper",
            "coin",
            "piece",
        }:
            continue
        verb = match.group("verb").casefold()
        direction = "in" if re.fullmatch(
            _ACQUISITION_VERBS,
            verb,
            re.IGNORECASE,
        ) else "out"
        statements.append((direction, int(match.group("quantity")), descriptor))
    return tuple(statements)


def _commerce_name_matches(descriptor: str, row_name: str) -> bool:
    stated = _resource_tokens(descriptor) - _COMMERCE_GENERIC_TOKENS
    concrete = _resource_tokens(row_name) - _COMMERCE_GENERIC_TOKENS
    return bool(stated & concrete)


def _commerce_row_contract_mismatch(
    prepared: Sequence[PreparedCharacterAction],
    effective: Mapping[Tuple[str, str, str], int],
) -> Optional[str]:
    """Require a concrete row on paid acquisitions and compensated disposals."""
    by_path: Dict[str, List[PreparedCharacterAction]] = {}
    for item in prepared:
        by_path.setdefault(item.plan.canonical_path, []).append(item)

    for path, items in by_path.items():
        currency_delta = sum(
            effective.get((path, "currency", denomination), 0) * multiplier
            for denomination, multiplier in _DENOMINATIONS.items()
        )
        if not currency_delta:
            continue
        statements = tuple(
            statement
            for item in items
            for statement in _commerce_item_statements(item.changes)
        )
        for direction, quantity, descriptor in statements:
            expected_sign = 1 if direction == "in" else -1
            if (direction == "in" and currency_delta >= 0) or (
                direction == "out" and currency_delta <= 0
            ):
                continue
            matching = [
                (family, name, delta)
                for (delta_path, family, name), delta in effective.items()
                if delta_path == path
                and family in {"equipment", "ammunition"}
                and delta * expected_sign > 0
                and _commerce_name_matches(descriptor, name)
            ]
            if matching and sum(abs(delta) for _family, _name, delta in matching) >= quantity:
                continue

            family = (
                "ammunition"
                if _resource_tokens(descriptor) & _AMMUNITION_TOKENS
                else "equipment"
            )
            canonical_name = descriptor
            current = 0
            before = items[0].plan.pre_image
            field, name_field = (
                ("equipment", "item_name")
                if family == "equipment"
                else ("ammunition", "name")
            )
            existing = [
                row
                for row in before.get(field) or []
                if isinstance(row, dict)
                and _commerce_name_matches(
                    descriptor,
                    str(row.get(name_field) or ""),
                )
            ]
            if len(existing) == 1:
                canonical_name = str(existing[0].get(name_field))
                current = _strict_nonnegative_int(
                    existing[0].get("quantity", 1),
                    f"{field}.{_normalized_name(canonical_name)}.quantity",
                )
            signed_delta = quantity * expected_sign
            return (
                f"commerce {('acquisition' if direction == 'in' else 'disposal')} "
                f"of stated item {json.dumps(descriptor, ensure_ascii=False)} "
                "has no matching concrete resource row; required family "
                f"{family}, canonical {name_field}="
                f"{json.dumps(canonical_name, ensure_ascii=False)}, required "
                f"signed row delta {signed_delta:+d}, current {current}, "
                f"required final {current + signed_delta}. Description-only "
                "edits do not count as resource movement"
            )
    return None


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
    *,
    check_asset_rows: bool = True,
) -> Optional[str]:
    """Compare explicit positive action facts to the batch's merged finals."""
    try:
        effective = _effective_same_character_asset_deltas(prepared)
    except CharacterTransferError as exc:
        return str(exc)

    commerce_mismatch = _commerce_row_contract_mismatch(prepared, effective)
    if commerce_mismatch:
        return commerce_mismatch

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
            if check_asset_rows
            and key[0] == path
            and key[1] != "currency"
            and quantity > 0
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
                    descriptor = generic_matches[0][1].strip().casefold()
                    first_word = re.match(r"[a-z]+", descriptor)
                    if not first_word or first_word.group(0) not in (
                        _NON_QUANTITY_UNIT_WORDS
                    ):
                        key = unmatched[0]
                        stated[key] = stated.get(key, 0) + int(
                            generic_matches[0][0]
                        )

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
    *,
    accepted_noncharacter_deltas=(),
) -> Optional[str]:
    paths = [item.plan.canonical_path for item in component]
    if len(paths) != len(set(paths)):
        return "a transfer resolves more than once to the same character"

    accepted = {}
    accepted_currency = {}
    for value in accepted_noncharacter_deltas:
        if not isinstance(value, tuple) or len(value) != 4:
            return "planned non-character resource fact is malformed"
        path, family, name, quantity = value
        if family == "currency":
            if name not in _DENOMINATIONS:
                return "planned non-character currency fact is malformed"
            accepted_currency[path] = accepted_currency.get(path, 0) + (
                quantity * _DENOMINATIONS[name]
            )
            continue
        accepted[value] = accepted.get(value, 0) + 1
    for path, quantity in accepted_currency.items():
        if quantity:
            value = (path, "currency", "currency", quantity)
            accepted[value] = accepted.get(value, 0) + 1
    grouped: Dict[Tuple[str, str], List[AssetDelta]] = {}
    for item in component:
        for delta in concrete_asset_deltas(item.plan):
            accepted_key = (
                item.plan.canonical_path,
                delta.family,
                delta.name,
                delta.quantity,
            )
            if accepted.get(accepted_key, 0):
                accepted[accepted_key] -= 1
                continue
            grouped.setdefault(delta.lookup_key, []).append(delta)
    if any(accepted.values()):
        return "planned non-character resource fact is absent from the character image"
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


def _canonicalize_unambiguous_transfer_rows(
    component: Sequence[PreparedCharacterAction],
    mismatch: str,
) -> Tuple[Tuple[PreparedCharacterAction, ...], Tuple[str, ...]]:
    """Preserve exact outgoing equipment/ammunition rows after model repair.

    The model and T105 still choose participants, edges, names, and quantities.
    This seam can only replace a receiver row when one exact outgoing row and
    one same-name incoming row already prove an equal conserved quantity.
    """
    if not mismatch.endswith(
        " has ambiguous mechanical identity"
    ):
        return tuple(component), ()

    row_deltas = [
        (item, delta)
        for item in component
        for delta in concrete_asset_deltas(item.plan)
        if delta.family in {"equipment", "ammunition"}
    ]
    grouped = {}
    for value in row_deltas:
        grouped.setdefault(value[1].lookup_key, []).append(value)

    updated = {item.index: item for item in component}
    advisories = []
    for (family, name), values in sorted(grouped.items()):
        outgoing = [value for value in values if value[1].quantity < 0]
        incoming = [value for value in values if value[1].quantity > 0]
        if len(outgoing) != 1 or len(incoming) != 1:
            continue
        giver, removed = outgoing[0]
        receiver, added = incoming[0]
        if -removed.quantity != added.quantity:
            continue

        field, name_field = (
            ("equipment", "item_name")
            if family == "equipment"
            else ("ammunition", "name")
        )
        source_rows = [
            row
            for row in giver.plan.pre_image.get(field, []) or []
            if isinstance(row, dict)
            and _normalized_name(row.get(name_field)) == name
        ]
        receiver_current = updated[receiver.index]
        receiver_before_rows = receiver_current.plan.pre_image.get(field, []) or []
        receiver_after_rows = receiver_current.plan.post_image.get(field, []) or []
        if (
            len(source_rows) != 1
            or not isinstance(receiver_before_rows, list)
            or not isinstance(receiver_after_rows, list)
        ):
            continue
        before_named = [
            copy.deepcopy(row)
            for row in receiver_before_rows
            if isinstance(row, dict)
            and _normalized_name(row.get(name_field)) == name
        ]
        after_named = [
            row
            for row in receiver_after_rows
            if isinstance(row, dict)
            and _normalized_name(row.get(name_field)) == name
        ]
        if len(before_named) > 1 or len(after_named) != 1:
            continue

        canonical = copy.deepcopy(source_rows[0])
        if family == "equipment":
            canonical["quantity"] = added.quantity
            canonical["equipped"] = False
            replacement_rows, _identity_advisories = consolidate_equipment_rows(
                before_named + [canonical]
            )
            if len(replacement_rows) != 1:
                continue
        else:
            if before_named and inventory_metadata(
                before_named[0], "name"
            ) != inventory_metadata(canonical, "name"):
                continue
            current_quantity = (
                _strict_nonnegative_int(
                    before_named[0].get("quantity"),
                    f"ammunition.{name}.quantity",
                )
                if before_named
                else 0
            )
            canonical["quantity"] = current_quantity + added.quantity
            replacement_rows = [canonical]

        rebuilt = []
        replaced = False
        for row in receiver_after_rows:
            if (
                isinstance(row, dict)
                and _normalized_name(row.get(name_field)) == name
            ):
                if not replaced:
                    rebuilt.extend(copy.deepcopy(replacement_rows))
                    replaced = True
                continue
            rebuilt.append(copy.deepcopy(row))
        post_image = copy.deepcopy(receiver_current.plan.post_image)
        post_image[field] = rebuilt
        advisory = f"transfer_metadata_canonicalized:{name}"
        updated_plan = replace(
            receiver_current.plan,
            post_image=post_image,
            field_facts=tuple(
                _field_change_facts(receiver_current.plan.pre_image, post_image)
            ),
            advisories=tuple(
                sorted(set(receiver_current.plan.advisories + (advisory,)))
            ),
        )
        updated[receiver.index] = replace(receiver_current, plan=updated_plan)
        advisories.append(advisory)
        warning(f"INVENTORY: {advisory}", category="character_updates")
    return tuple(updated[item.index] for item in component), tuple(advisories)


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
    correction: Optional[Any] = None,
) -> Tuple[PreparedCharacterAction, ...]:
    prepared = []
    for index, action in indexed_actions:
        changes = _action_changes(action)
        request = changes
        action_correction = (
            correction.get(index)
            if isinstance(correction, Mapping)
            else correction
        )
        if action_correction:
            request = (
                f"{changes}\n\nJOINT TRANSFER CORRECTION (one final attempt): "
                f"{action_correction}. Return the exact final values needed so every "
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


def _reprepare_selected_actions(
    prepared: Sequence[PreparedCharacterAction],
    party: Mapping[str, Any],
    correction: str,
    action_indices,
) -> Tuple[PreparedCharacterAction, ...]:
    """Re-run only correction-owning actions; preserve every sibling plan."""
    selected = {
        value for value in action_indices if type(value) is int
    }
    if not selected:
        return tuple(prepared)
    corrected = _prepare_actions(
        tuple(
            (item.index, item.action)
            for item in prepared
            if item.index in selected
        ),
        party,
        correction={index: correction for index in selected},
    )
    by_index = {item.index: item for item in corrected}
    return tuple(by_index.get(item.index, item) for item in prepared)


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
    resource_intent: str = "",
    resource_planner_call_budget=None,
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
        preliminary_planning_decision = None
        if enable_resource_planning:
            import model_config
            from core.managers.resource_transaction_planning import (
                route_resource_transaction,
            )

            preliminary_planning_decision = route_resource_transaction(
                prepared,
                tuple(resource_storage_plans),
                provider=model_config.get_provider(),
            )
        check_asset_stated_values = not (
            preliminary_planning_decision
            and preliminary_planning_decision.requires_planning
        )
        failed_stage = "party_attributed_transfer_validation"
        prepared = _repair_party_attributed_requirements(
            prepared,
            party_tracker_data,
        )
        failed_stage = "explicit_stated_value_contract"
        stated_value_mismatch = _explicit_removal_contract_mismatch(prepared)
        if not stated_value_mismatch:
            stated_value_mismatch = _explicit_acquisition_contract_mismatch(
                prepared,
                check_asset_rows=check_asset_stated_values,
            )
        if stated_value_mismatch:
            correction = (
                f"{stated_value_mismatch}. Explicit numbered resource changes "
                "must produce that exact concrete increase or decrease; never "
                "duplicate, clamp, floor, partially apply, or substitute "
                "another resource"
            )
            commerce_indices = {
                item.index
                for item in prepared
                if _commerce_item_statements(item.changes)
            }
            if stated_value_mismatch.startswith("commerce "):
                corrected = _reprepare_selected_actions(
                    prepared,
                    party_tracker_data,
                    correction,
                    commerce_indices,
                )
            else:
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
                    _explicit_acquisition_contract_mismatch(
                        corrected,
                        check_asset_rows=check_asset_stated_values,
                    )
                )
            if remaining_stated_value_mismatch:
                raise CharacterTransferError(
                    "explicit stated-value correction failed safely: "
                    f"{remaining_stated_value_mismatch}"
                )
            prepared = corrected
            shape_corrected_indices = {item.index for item in prepared}
        failed_stage = "transfer_shape_validation"
        shape_mismatch = _batch_transfer_shape_mismatch(prepared)
        if shape_mismatch:
            if shape_corrected_indices:
                raise CharacterTransferError(
                    f"transfer correction failed safely: {shape_mismatch}"
                )
            correction = _participant_scoped_corrections(prepared)
            corrected = _prepare_actions(
                tuple((item.index, item.action) for item in prepared),
                party_tracker_data,
                correction=correction,
            )
            remaining_shape_mismatch = _batch_transfer_shape_mismatch(corrected)
            if remaining_shape_mismatch and not enable_resource_planning:
                raise CharacterTransferError(
                    "transfer correction failed safely: "
                    f"{remaining_shape_mismatch}"
                )
            prepared = corrected
            shape_corrected_indices = {item.index for item in prepared}
        planning_result = None
        planned_noncharacter_deltas = ()
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
                player_intent=resource_intent,
                planner_call_budget=resource_planner_call_budget,
            )
            prepared = planning_result.character_actions
            resource_storage_plans = planning_result.storage_plans
            planned_noncharacter_deltas = getattr(
                planning_result,
                "non_character_deltas",
                (),
            )
            failed_stage = "transfer_shape_validation"
            shape_mismatch = _batch_transfer_shape_mismatch(prepared)
            if shape_mismatch:
                raise CharacterTransferError(
                    "planned transfer still violates conservation: "
                    f"{shape_mismatch}"
                )
        validation_prepared = prepared
        if planning_result is not None:
            from core.managers.resource_transaction_planning import (
                routed_character_validation_actions,
            )

            validation_prepared = routed_character_validation_actions(prepared)
        by_index = {item.index: item for item in validation_prepared}
        components = _candidate_components(validation_prepared)

        corrected_components = {}
        failed_stage = "transfer_component_validation"
        for indices in components:
            component = tuple(by_index[index] for index in indices)
            component_paths = {item.plan.canonical_path for item in component}
            component_noncharacter_deltas = tuple(
                value
                for value in planned_noncharacter_deltas
                if value[0] in component_paths
            )
            mismatch = _validate_transfer_component(
                component,
                accepted_noncharacter_deltas=component_noncharacter_deltas,
            )
            if mismatch:
                if set(indices).issubset(shape_corrected_indices):
                    corrected = component
                else:
                    correction = _participant_scoped_corrections(component)
                    corrected = _prepare_actions(
                        tuple((item.index, item.action) for item in component),
                        party_tracker_data,
                        correction=correction,
                    )
                    mismatch = _validate_transfer_component(
                        corrected,
                        accepted_noncharacter_deltas=component_noncharacter_deltas,
                    )
                if mismatch:
                    corrected, _canonicalization_advisories = (
                        _canonicalize_unambiguous_transfer_rows(
                            corrected,
                            mismatch,
                        )
                    )
                    mismatch = _validate_transfer_component(
                        corrected,
                        accepted_noncharacter_deltas=component_noncharacter_deltas,
                    )
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
        prepared_actions = _with_party_currency_aggregate_advisory(
            prepared_actions,
            party_tracker_data,
        )
        advised_by_index = {item.index: item for item in prepared_actions}
        units = [
            (
                index,
                tuple(advised_by_index.get(item.index, item) for item in unit),
                operation,
            )
            for index, unit, operation in units
        ]
        prepared = prepared_actions
        if prepare_only:
            return {
                "status": "continue",
                "success": True,
                "needs_update": bool(prepared_actions),
                "prepared_actions": prepared_actions,
                "prepared_indices": [item.index for item in prepared_actions],
                "storage_plans": tuple(resource_storage_plans),
                "resource_planning": planning_result,
                "external_contract": (
                    getattr(planning_result, "external_contract", None)
                    if planning_result is not None
                    else None
                ),
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
                        correction = _participant_scoped_corrections(refreshed)
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
    *,
    resource_intent: str = "",
    resource_planner_call_budget=None,
) -> Dict[str, Any]:
    """Return transfer-validated response images without changing files."""
    return commit_prepared_character_actions(
        prepared,
        party_tracker_data,
        prepare_only=True,
        resource_storage_plans=tuple(storage_plans),
        enable_resource_planning=True,
        resource_intent=resource_intent,
        resource_planner_call_budget=resource_planner_call_budget,
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
