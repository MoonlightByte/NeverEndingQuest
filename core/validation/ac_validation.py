# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Narrow deterministic Armor Class evidence and advisory metadata.

The saved character sheet remains the base-stat authority. This module only
computes that base when the existing structured evidence is complete and
unambiguous; temporary/effective modifiers stay in the effects projection.
Ambiguous and homebrew cases remain model-authored.
"""

from __future__ import annotations

import copy
import hashlib
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock


AC_ADVISORY_VERSION = 1
AC_ADVISORY_PATH = os.path.join("modules", "runtime_ac_validation.json")
MAX_AC_ADVISORIES = 512
_BODY_ARMOR_CATEGORIES = frozenset(("light", "medium", "heavy"))
_AC_TARGETS = frozenset(("ac", "armorclass", "armor class"))
_AC_TEXT = re.compile(
    r"\b(?:armor\s+class|ac|unarmored\s+defen[cs]e|natural\s+armor)\b",
    flags=re.IGNORECASE,
)
_VALID_STATUSES = frozenset(("deterministic", "model", "unavailable"))
_VALID_REASONS = frozenset(
    ("structured_armor", "ambiguous_evidence", "model_validation_failed")
)


class ACConfidence(str, Enum):
    CONFIDENT = "confident"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ACComputation:
    confidence: ACConfidence
    armor_class: Optional[int]
    reasons: Tuple[str, ...] = ()


def _strict_int(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _normalized_category(item: Mapping[str, Any]) -> str:
    value = item.get("armor_category")
    return value.strip().casefold() if isinstance(value, str) else ""


def is_complete_structured_ac_item(item: Any) -> bool:
    """Return whether one row safely supports the B1/B2 AC arithmetic rail."""
    if not isinstance(item, Mapping):
        return False
    category = _normalized_category(item)
    if category in _BODY_ARMOR_CATEGORIES:
        return (
            item.get("item_type") == "armor"
            and _strict_int(item.get("ac_base"), 0, 30)
            and "dex_limit" in item
            and (
                item.get("dex_limit") is None
                or _strict_int(item.get("dex_limit"), 0, 10)
            )
            and _strict_int(item.get("ac_bonus"), -5, 10)
        )
    if category == "shield":
        return item.get("item_type") == "armor" and _strict_int(
            item.get("ac_bonus"), -5, 10
        )
    return False


def _text_has_ac_evidence(value: Any) -> bool:
    return isinstance(value, str) and bool(_AC_TEXT.search(value))


def _effect_targets_ac(effect: Any) -> bool:
    if not isinstance(effect, Mapping):
        return False
    target = effect.get("target") or effect.get("stat")
    if isinstance(target, str):
        normalized_target = target.replace("_", " ").casefold()
        if normalized_target in _AC_TARGETS or _text_has_ac_evidence(target):
            return True
    modifiers = effect.get("modifiers")
    if isinstance(modifiers, list) and any(
        isinstance(modifier, Mapping)
        and str(modifier.get("stat") or "").replace("_", " ").casefold() in _AC_TARGETS
        for modifier in modifiers
    ):
        return True
    return _text_has_ac_evidence(effect.get("name")) or _text_has_ac_evidence(
        effect.get("description")
    )


def _item_has_ac_evidence(item: Mapping[str, Any]) -> bool:
    if item.get("item_type") == "armor" or any(
        field in item
        for field in ("armor_category", "ac_base", "ac_bonus", "dex_limit")
    ):
        return True
    if _text_has_ac_evidence(item.get("item_name")) or _text_has_ac_evidence(
        item.get("description")
    ):
        return True
    effects = item.get("effects")
    return isinstance(effects, list) and any(
        _effect_targets_ac(effect) for effect in effects
    )


def _record_text(record: Any) -> str:
    if isinstance(record, str):
        return record
    if not isinstance(record, Mapping):
        return ""
    return "%s %s" % (record.get("name", ""), record.get("description", ""))


def _record_has_ac_evidence(record: Any) -> bool:
    if _text_has_ac_evidence(_record_text(record)):
        return True
    if not isinstance(record, Mapping):
        return False
    if _effect_targets_ac(record):
        return True
    effects = record.get("effects")
    return isinstance(effects, list) and any(
        _effect_targets_ac(effect) for effect in effects
    )


def _exact_defense_features(sheet: Mapping[str, Any]) -> Tuple[int, bool]:
    exact = 0
    ambiguous = False
    features = sheet.get("classFeatures") or []
    if not isinstance(features, list):
        return 0, True
    for feature in features:
        text = _record_text(feature)
        name = feature.get("name") if isinstance(feature, Mapping) else None
        if (
            isinstance(name, str)
            and name.strip().casefold() == "fighting style: defense"
        ):
            exact += 1
        elif "fighting style: defense" in text.casefold() or _record_has_ac_evidence(
            feature
        ):
            ambiguous = True
    return exact, ambiguous


def _derived_effect_is_redundant(
    effect: Mapping[str, Any],
    shields: Tuple[Mapping[str, Any], ...],
    has_defense: bool,
) -> bool:
    name = str(effect.get("name") or "").strip().casefold()
    source = str(effect.get("source") or "").strip().casefold()
    value = effect.get("value")
    if (
        has_defense
        and name == "fighting style: defense"
        and source == "class feature"
        and value == 1
    ):
        return True
    if name != "shield ac bonus" or len(shields) != 1:
        return False
    shield = shields[0]
    return (
        value == shield.get("ac_bonus")
        and source == str(shield.get("item_name") or "").strip().casefold()
    )


def compute_structured_base_ac(sheet: Any) -> ACComputation:
    """Compute base AC only for the locked B1 confidence domain."""
    if not isinstance(sheet, Mapping):
        return ACComputation(ACConfidence.AMBIGUOUS, None, ("invalid_sheet",))
    equipment = sheet.get("equipment") or []
    abilities = sheet.get("abilities") or {}
    if not isinstance(equipment, list) or not isinstance(abilities, Mapping):
        return ACComputation(ACConfidence.AMBIGUOUS, None, ("invalid_evidence",))
    dexterity = abilities.get("dexterity")
    if not _strict_int(dexterity, 1, 30):
        return ACComputation(ACConfidence.AMBIGUOUS, None, ("invalid_dexterity",))

    body = []
    shields = []
    reasons = []
    for item in equipment:
        if not isinstance(item, Mapping):
            reasons.append("malformed_equipment")
            continue
        if item.get("equipped") is not True:
            continue
        category = _normalized_category(item)
        if category in _BODY_ARMOR_CATEGORIES:
            if is_complete_structured_ac_item(item):
                body.append(item)
            else:
                reasons.append("incomplete_body_armor")
        elif category == "shield":
            if is_complete_structured_ac_item(item):
                shields.append(item)
            else:
                reasons.append("incomplete_shield")
        elif _item_has_ac_evidence(item):
            reasons.append("other_ac_equipment")
        effects = item.get("effects")
        if isinstance(effects, list) and any(
            _effect_targets_ac(effect) for effect in effects
        ):
            reasons.append("equipped_ac_effect")

    if len(body) != 1:
        reasons.append("body_armor_count")
    if len(shields) > 1:
        reasons.append("shield_count")

    class_text = str(sheet.get("class") or "").casefold()
    if re.search(r"\b(?:barbarian|monk)\b", class_text):
        reasons.append("unarmored_formula")
    defense_count, feature_ambiguity = _exact_defense_features(sheet)
    if defense_count > 1 or feature_ambiguity:
        reasons.append("other_ac_feature")

    for field, reason in (
        ("racialTraits", "natural_armor_evidence"),
        ("feats", "ac_feat_evidence"),
    ):
        records = sheet.get(field) or []
        if not isinstance(records, list):
            reasons.append("invalid_%s" % field)
        elif any(_record_has_ac_evidence(record) for record in records):
            reasons.append(reason)

    for field in ("temporaryEffects", "activeEffects"):
        effects = sheet.get(field) or []
        if not isinstance(effects, list):
            reasons.append("invalid_%s" % field)
        elif any(_effect_targets_ac(effect) for effect in effects):
            reasons.append("conditional_ac_effect")

    derived_effects = sheet.get("equipment_effects") or []
    if not isinstance(derived_effects, list):
        reasons.append("invalid_equipment_effects")
    else:
        shield_tuple = tuple(shields)
        for effect in derived_effects:
            if not isinstance(effect, Mapping):
                reasons.append("malformed_equipment_effect")
                continue
            if _effect_targets_ac(effect) and not _derived_effect_is_redundant(
                effect,
                shield_tuple,
                defense_count == 1,
            ):
                reasons.append("other_equipment_ac_effect")

    if reasons:
        return ACComputation(
            ACConfidence.AMBIGUOUS,
            None,
            tuple(sorted(set(reasons))),
        )

    armor = body[0]
    dexterity_modifier = (dexterity - 10) // 2
    dexterity_limit = armor.get("dex_limit")
    if _normalized_category(armor) == "heavy":
        applied_dexterity = 0
    else:
        applied_dexterity = (
            dexterity_modifier
            if dexterity_limit is None
            else min(dexterity_modifier, dexterity_limit)
        )
    armor_class = (
        int(armor["ac_base"])
        + int(armor["ac_bonus"])
        + applied_dexterity
        + sum(int(shield["ac_bonus"]) for shield in shields)
        + (1 if defense_count == 1 else 0)
    )
    if not 1 <= armor_class <= 100:
        return ACComputation(
            ACConfidence.AMBIGUOUS,
            None,
            ("computed_ac_out_of_range",),
        )
    return ACComputation(
        ACConfidence.CONFIDENT,
        armor_class,
        ("structured_armor",),
    )


def _advisory_identity(character_data: Mapping[str, Any]) -> str:
    material = "\0".join(
        (
            str(character_data.get("name") or "").strip().casefold(),
            str(character_data.get("character_role") or "").strip().casefold(),
            str(character_data.get("character_type") or "").strip().casefold(),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _load_store(path: str) -> Dict[str, Any]:
    value = safe_json_load(path)
    if not isinstance(value, dict) or value.get("version") != AC_ADVISORY_VERSION:
        return {"version": AC_ADVISORY_VERSION, "characters": {}}
    characters = value.get("characters")
    if not isinstance(characters, dict):
        return {"version": AC_ADVISORY_VERSION, "characters": {}}
    return {"version": AC_ADVISORY_VERSION, "characters": dict(characters)}


def record_ac_validation_status(
    character_data: Mapping[str, Any],
    status: str,
    reason: str,
    path: str = AC_ADVISORY_PATH,
) -> bool:
    """Replace one advisory status atomically; never mutate the character."""
    if status not in _VALID_STATUSES or reason not in _VALID_REASONS:
        raise ValueError("invalid AC validation advisory")
    try:
        with path_transaction_lock(
            path,
            suffix=".validation-cache.lock",
            timeout_seconds=2.0,
        ) as acquired:
            if acquired is None:
                return False
            store = _load_store(path)
            entries = store["characters"]
            identity = _advisory_identity(character_data)
            entries[identity] = {"status": status, "reason": reason}
            if len(entries) > MAX_AC_ADVISORIES:
                for key in sorted(entries):
                    if key != identity and len(entries) > MAX_AC_ADVISORIES:
                        entries.pop(key, None)
            return bool(safe_write_json(path, store))
    except Exception:
        return False


def read_ac_validation_status(
    character_data: Mapping[str, Any],
    path: str = AC_ADVISORY_PATH,
) -> Optional[Dict[str, str]]:
    if not isinstance(character_data, Mapping):
        return None
    record = _load_store(path)["characters"].get(_advisory_identity(character_data))
    if (
        not isinstance(record, dict)
        or record.get("status") not in _VALID_STATUSES
        or record.get("reason") not in _VALID_REASONS
    ):
        return None
    return {"status": record["status"], "reason": record["reason"]}


def attach_ac_validation_advisory(
    character_data: Mapping[str, Any],
    path: str = AC_ADVISORY_PATH,
) -> Dict[str, Any]:
    """Return an additive UI envelope copy; the schema-bound sheet is untouched."""
    result = copy.deepcopy(dict(character_data))
    status = read_ac_validation_status(character_data, path=path)
    if status is not None:
        result["acValidation"] = status
    return result
