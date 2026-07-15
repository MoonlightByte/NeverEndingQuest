# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Community Tools - Character Validator
Copyright (c) 2024 MoonlightByte
Licensed under Apache License 2.0

See LICENSE-APACHE file for full terms.
"""

# ============================================================================
# CHARACTER_VALIDATOR.PY - AI-POWERED CHARACTER DATA VALIDATION
# ============================================================================
#
# ARCHITECTURE ROLE: AI Integration Layer - Character Data Validation
#
# This module provides intelligent AI-powered character validation ensuring data
# integrity and 5th edition rule compliance through GPT-4 reasoning and validation,
# with automatic correction capabilities for common data inconsistencies.
#
# KEY RESPONSIBILITIES:
# - AI-driven character data validation with 5th edition rule compliance
# - Intelligent armor class calculation verification and correction
# - Inventory item categorization and equipment conflict resolution
# - Currency consolidation preserving player agency over containers
# - Automatic data format standardization and correction
# - Character sheet integrity validation across all character components
# - Integration with character effects validation for comprehensive validation
#

"""
AI-Powered Character Validator

An intelligent validation system that uses AI to ensure character data integrity
based on the 5th edition of the world's most popular role playing game rules.

Uses GPT-4.1 to intelligently validate and auto-correct:
- Armor Class calculations
- Inventory item categorization (prevents arrows as "miscellaneous", etc.)
- Currency consolidation (consolidates loose coins while preserving valuables)
- Equipment conflicts  
- Temporary effects (future)
- Stat bonuses (future)

INVENTORY VALIDATION SYSTEM:
Solves GitHub issue #45 - inconsistent ration storage format across characters.
Two-pronged approach:
1. PREVENTIVE: Enhanced AI prompts prevent future categorization errors
2. CORRECTIVE: AI validation fixes existing miscategorized items

The system uses the same deep merge strategy as the main character updater,
ensuring atomic file operations and preventing data corruption.

The AI reasons through the rules rather than following hardcoded logic,
making it flexible and adaptable to any character structure or edge case.
"""

import json
import copy
import logging
import os
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from core.ai import api_client
from utils.character_sheet_contract import repair_required_ammunition_field
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T051", "core/validation/character_validator.py", 1946)
register_callsite("T052", "core/validation/character_validator.py", 2085)
register_callsite("T053", "core/validation/character_validator.py", 2936)
register_callsite("T054", "core/validation/character_validator.py", 3746)

CHARACTER_VALIDATOR_SCHEMA = {
    "required": [
        "validated_character_data",
        "corrections_made",
        "ac_calculation_breakdown",
    ],
    "properties": {
        "validated_character_data": {"type": "object"},
        "corrections_made": {"type": "array"},
        "ac_calculation_breakdown": {
            "type": "object",
            "required": [
                "base_armor",
                "dex_modifier",
                "shield_bonus",
                "fighting_style_bonus",
                "total_ac",
            ],
            "properties": {
                "base_armor": {"type": "string"},
                "dex_modifier": {"type": ["string", "integer", "number"]},
                "shield_bonus": {"type": ["string", "integer", "number"]},
                "fighting_style_bonus": {"type": ["string", "integer", "number"]},
                "total_ac": {"type": ["string", "integer", "number"]},
            },
        },
    },
}


class CharacterValidationResponseError(ValueError):
    """A provider response was readable text but violated a validator contract."""


class CharacterValidationStatus(str, Enum):
    """Machine-readable outcome for a character-validation attempt."""

    CHANGED = "changed"
    NO_CHANGE = "no_change"
    FAILED = "failed"


@dataclass(frozen=True)
class CharacterValidationResult:
    """Explicit validation outcome used by persistence-aware callers.

    The legacy validator methods still return only ``data``.  Their ``*_with_result``
    counterparts return this object so callers can distinguish an authoritative
    no-op from retry exhaustion without comparing two dictionaries.
    """

    data: Dict[str, Any]
    status: CharacterValidationStatus
    error: Optional[str] = None
    _data_changed: Optional[bool] = None

    @property
    def success(self) -> bool:
        return self.status is not CharacterValidationStatus.FAILED

    @property
    def changed(self) -> bool:
        if self._data_changed is not None:
            return self._data_changed
        return self.status is CharacterValidationStatus.CHANGED


VALID_INVENTORY_ITEM_TYPES = frozenset({
    "weapon",
    "armor",
    "ammunition",
    "consumable",
    "equipment",
    "miscellaneous",
})
VALID_CURRENCY_FIELDS = frozenset({
    "platinum",
    "gold",
    "electrum",
    "silver",
    "copper",
})


def _validation_result(
    original_data: Dict[str, Any],
    validated_data: Dict[str, Any],
) -> CharacterValidationResult:
    status = (
        CharacterValidationStatus.NO_CHANGE
        if validated_data == original_data
        else CharacterValidationStatus.CHANGED
    )
    result_data = original_data if status is CharacterValidationStatus.NO_CHANGE else validated_data
    return CharacterValidationResult(
        result_data,
        status,
        _data_changed=status is CharacterValidationStatus.CHANGED,
    )


def _failed_validation_result(
    original_data: Dict[str, Any],
    exc: BaseException,
    validated_data: Optional[Dict[str, Any]] = None,
) -> CharacterValidationResult:
    result_data = validated_data if validated_data is not None else original_data
    changed = result_data != original_data
    if not changed:
        result_data = original_data
    return CharacterValidationResult(
        result_data,
        CharacterValidationStatus.FAILED,
        str(exc),
        _data_changed=changed,
    )


def _normalized_name(value: Any) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _require_string_list(value: Any, path: str) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CharacterValidationResponseError(
            f"{path} must be an array of strings"
        )
    return value


def _require_contract_integer(
    value: Any,
    path: str,
    *,
    minimum: Optional[int] = None,
) -> int:
    """Return a contract integer while rejecting booleans and fractions."""

    normalized = value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or not stripped.lstrip("+-").isdigit():
            raise CharacterValidationResponseError(f"{path} must be an integer")
        normalized = int(stripped)
    elif isinstance(value, float) and value.is_integer():
        normalized = int(value)

    if type(normalized) is not int:
        raise CharacterValidationResponseError(f"{path} must be an integer")
    if minimum is not None and normalized < minimum:
        raise CharacterValidationResponseError(
            f"{path} must be at least {minimum}"
        )
    return normalized


def _source_items_by_name(
    items: Any,
    path: str,
    *,
    name_field: str = "item_name",
    reject_duplicates: bool = False,
) -> Dict[str, Dict[str, Any]]:
    if not isinstance(items, list):
        raise CharacterValidationResponseError(f"{path} must be an array")
    source: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CharacterValidationResponseError(
                f"{path}[{index}] must be an object"
            )
        name = _normalized_name(item.get(name_field))
        if name:
            if reject_duplicates and name in source:
                raise CharacterValidationResponseError(
                    f"{path} contains duplicate normalized name "
                    f"'{item.get(name_field)}'"
                )
            source.setdefault(name, item)
    return source


def _require_unique_source_ammunition(items: Any, path: str) -> None:
    """Ensure the ammunition merge cannot collapse or drop source identities."""

    if not isinstance(items, list):
        raise CharacterValidationResponseError(f"{path} must be an array")
    seen_names = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise CharacterValidationResponseError(
                f"{path}[{index}] must be an object"
            )
        normalized_name = _normalized_name(item.get("name"))
        if not normalized_name:
            raise CharacterValidationResponseError(
                f"{path}[{index}] requires a nonempty name"
            )
        # Standard ammunition has a singular/plural canonical identity.  The
        # downstream merge uses that identity, so fail closed before a pair
        # such as ``Arrow``/``Arrows`` can be collapsed behind the parser.
        source_identity = (
            _canonical_ammunition_name(normalized_name) or normalized_name
        )
        if source_identity in seen_names:
            raise CharacterValidationResponseError(
                f"{path} contains duplicate normalized/canonical name "
                f"'{item.get('name')}'"
            )
        seen_names.add(source_identity)


_CURRENCY_ALIASES = {
    "platinum": ("platinum", "pp"),
    "gold": ("gold", "gp"),
    "electrum": ("electrum", "ep"),
    "silver": ("silver", "sp"),
    "copper": ("copper", "cp"),
}
_SPECIAL_AMMUNITION_MARKERS = (
    "+1", "+2", "+3", "flaming", "frost", "slaying", "silvered",
    "adamantine", "magical", "enchanted",
)
_AMMUNITION_NAMES = (
    ("crossbow bolts", ("crossbow bolt", "crossbow bolts")),
    ("sling bullets", ("sling bullet", "sling bullets")),
    ("blowgun needles", ("blowgun needle", "blowgun needles")),
    ("arrows", ("arrow", "arrows")),
    ("bolts", ("bolt", "bolts")),
    ("bullets", ("bullet", "bullets")),
    ("darts", ("dart", "darts")),
    ("needles", ("needle", "needles")),
)
_NUMBER_WORD_TOKENS = frozenset({
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
    "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety", "hundred", "thousand",
})
_CURRENCY_SOURCE_TOKENS = _NUMBER_WORD_TOKENS.union({
    "a", "an", "the", "of", "with", "containing", "contains", "holding",
    "holds", "bag", "pouch", "purse", "stack", "pile", "bundle", "loose",
    "coin", "coins", "piece", "pieces", "currency", "money", "available",
    "emptied", "empty", "opened", "open", "collected", "from", "table",
    "small", "large", "leather", "canvas", "simple", "ordinary", "old",
    "platinum", "pp", "gold", "gp", "electrum", "ep", "silver", "sp",
    "copper", "cp",
})
_AMMUNITION_SOURCE_TOKENS = _NUMBER_WORD_TOKENS.union({
    "a", "an", "the", "of", "with", "containing", "contains", "holding",
    "holds", "bundle", "stack", "pile", "loose", "standard", "ordinary",
    "ammunition", "ammo", "arrow", "arrows", "bolt", "bolts", "crossbow",
    "bullet", "bullets", "sling", "needle", "needles", "blowgun", "dart",
    "darts", "quiver", "case", "full", "empty", "leather", "wooden",
    "simple", "ready", "to", "consolidate", "carrying", "carry", "for",
    "use", "bow", "bows", "longbow", "shortbow", "crossbows", "or", "x",
})
_CONTAINER_BOOLEAN_STATE_FIELDS = ("full", "is_full", "loaded")
_CONTAINER_COUNT_STATE_FIELDS = (
    "ammo_count", "arrow_count", "bolt_count", "current_load",
)
_CONTAINER_TEXT_STATE_FIELDS = ("container_state", "state")
_CONTAINER_STRUCTURED_CONTENT_FIELDS = ("contents", "contained_items")
_DESTRUCTIVE_SOURCE_BASE_FIELDS = frozenset({
    "item_name",
    "item_type",
    "description",
    "quantity",
    "equipped",
    "magical",
    "item_subtype",
})


def _reject_unsupported_number_words(
    texts: tuple,
    path: str,
) -> None:
    """Reject word quantities that the conservation parser cannot bind."""

    for text in texts:
        for token in re.findall(r"[a-z]+", text.casefold().replace("-", " ")):
            if token in _NUMBER_WORD_TOKENS:
                raise CharacterValidationResponseError(
                    f"{path} contains unsupported word quantity token '{token}'"
                )


def _source_text_is_pure(value: Any, allowed_tokens: frozenset) -> bool:
    """Accept only narrow, item-kind-specific prose for destructive evidence."""

    if value is None or value == "":
        return True
    if not isinstance(value, str):
        return False
    tokens = re.findall(r"[a-z]+|\d+", value.casefold().replace("-", " "))
    return bool(tokens) and all(token.isdigit() or token in allowed_tokens for token in tokens)


def _source_quantity(item: Dict[str, Any], path: str) -> int:
    return _require_contract_integer(item.get("quantity", 1), path, minimum=1)


def _explicit_source_quantity(
    item: Dict[str, Any],
    path: str,
) -> Optional[int]:
    """Return an explicitly persisted quantity, never an inferred default."""

    if "quantity" not in item:
        return None
    return _require_contract_integer(item["quantity"], path, minimum=1)


def _require_destructively_safe_source_item(
    item: Dict[str, Any],
    path: str,
) -> None:
    """Reject source metadata that a remove directive would silently discard."""

    for field, value in item.items():
        if field in _DESTRUCTIVE_SOURCE_BASE_FIELDS:
            continue
        if value not in (None, "", False, [], {}):
            raise CharacterValidationResponseError(
                f"{path} conservation rejects non-discardable metadata '{field}'"
            )

    if item.get("magical") not in (None, "", False):
        raise CharacterValidationResponseError(
            f"{path} conservation rejects magical value-bearing metadata"
        )
    if item.get("item_subtype") not in (None, ""):
        raise CharacterValidationResponseError(
            f"{path} conservation rejects non-discardable item_subtype metadata"
        )
    item_type = item.get("item_type")
    if item_type not in (None, "") and (
        not isinstance(item_type, str)
        or item_type.strip().casefold()
        not in VALID_INVENTORY_ITEM_TYPES.union({"currency"})
    ):
        raise CharacterValidationResponseError(
            f"{path} conservation rejects an unsupported item_type"
        )
    if "equipped" in item and type(item["equipped"]) is not bool:
        raise CharacterValidationResponseError(
            f"{path} conservation requires a boolean equipped field"
        )


def _parse_positive_amount(value: str, path: str) -> int:
    """Parse a positive integer with optional conventional thousands commas."""

    if "," in value and not re.fullmatch(r"\d{1,3}(?:,\d{3})+", value):
        raise CharacterValidationResponseError(
            f"{path} has an ambiguous numeric amount"
        )
    amount = int(value.replace(",", ""))
    if amount <= 0:
        raise CharacterValidationResponseError(
            f"{path} amount must be positive"
        )
    return amount


def _currency_evidence_from_item(
    item: Dict[str, Any],
    path: str,
) -> Dict[str, int]:
    """Return exact denomination totals encoded by a removable source item.

    Only common numeric forms are accepted. Word-only or value-estimate prose is
    intentionally treated as ambiguous so a model cannot manufacture a balance.
    """

    name = str(item.get("item_name", "")).casefold()
    description = str(item.get("description", "")).casefold()
    combined = f"{name} {description}"
    _reject_unsupported_number_words((name, description), path)
    if any(
        field in item and item[field] not in (None, "", [], {})
        for field in _CONTAINER_STRUCTURED_CONTENT_FIELDS
    ):
        return {}
    if any(
        marker in combined
        for marker in (
            "worth", "valued at", "value of", "locked", "sealed", "trapped",
            "unopened", "valuable", "closed container", "closed chest",
            "closed coffer", "closed strongbox", "closed vault",
        )
    ):
        return {}
    if not all(
        _source_text_is_pure(text, _CURRENCY_SOURCE_TOKENS)
        for text in (name, description)
    ):
        return {}
    if any(re.search(r"[+\-/]\s*\d", text) for text in (name, description)):
        raise CharacterValidationResponseError(
            f"{path} contains an ambiguous signed or ranged amount"
        )

    quantity = _source_quantity(item, f"{path}.quantity")
    evidence: Dict[str, int] = {}
    matched_amount_spans = {0: set(), 1: set()}
    amount_token = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    for denomination, aliases in _CURRENCY_ALIASES.items():
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        amount_pattern = re.compile(
            rf"(?<![\w.,+\-/])({amount_token})\s*(?:{alias_pattern})"
            rf"(?:\s*(?:pieces?|coins?))?\b",
            re.IGNORECASE,
        )
        amounts = set()
        amount_counts = [0, 0]
        for text_index, text in enumerate((name, description)):
            for match in amount_pattern.finditer(text):
                amount_counts[text_index] += 1
                amounts.add(
                    _parse_positive_amount(
                        match.group(1),
                        f"{path}.{denomination}",
                    )
                )
                matched_amount_spans[text_index].add(match.span(1))
        if len(amounts) > 1 or any(count > 1 for count in amount_counts):
            raise CharacterValidationResponseError(
                f"{path} has ambiguous {denomination} quantities"
            )
        if amounts:
            evidence[denomination] = next(iter(amounts)) * quantity
            continue

        normalized_name = re.sub(r"\s+", " ", name).strip()
        if any(
            normalized_name in {
                alias,
                f"{alias} piece",
                f"{alias} pieces",
                f"{alias} coin",
                f"{alias} coins",
            }
            for alias in aliases
        ):
            explicit_quantity = _explicit_source_quantity(
                item,
                f"{path}.quantity",
            )
            if explicit_quantity is not None:
                evidence[denomination] = explicit_quantity

    # If currency language is present, every digit group must belong to one of
    # the exact denomination amounts above. This rejects ranges, signs, broken
    # comma grouping, and unrelated counts instead of partially parsing them.
    currency_alias_pattern = "|".join(
        re.escape(alias)
        for aliases in _CURRENCY_ALIASES.values()
        for alias in aliases
    )
    if re.search(rf"\b(?:{currency_alias_pattern})\b", combined):
        for text_index, text in enumerate((name, description)):
            for match in re.finditer(r"\d[\d,]*", text):
                if match.span() not in matched_amount_spans[text_index]:
                    raise CharacterValidationResponseError(
                        f"{path} contains an ambiguous or unbound numeric amount"
                    )

    return evidence


def _canonical_ammunition_name(value: Any) -> Optional[str]:
    normalized = re.sub(r"\s+", " ", _normalized_name(value).replace("-", " "))
    for canonical, aliases in _AMMUNITION_NAMES:
        if normalized in aliases:
            return canonical
    return None


def _exact_metadata_equal(left: Any, right: Any) -> bool:
    """Compare JSON-like metadata without bool/int or other type coercion."""

    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        if left.keys() != right.keys():
            return False
        return all(
            _exact_metadata_equal(left[key], right[key])
            for key in left
        )
    if isinstance(left, (list, tuple)):
        return len(left) == len(right) and all(
            _exact_metadata_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        return False


def _ammunition_evidence_from_item(
    item: Dict[str, Any],
    path: str,
) -> Dict[str, int]:
    """Return exact standard-ammunition totals encoded by a source item."""

    name = str(item.get("item_name", "")).casefold()
    description = str(item.get("description", "")).casefold()
    combined = f"{name} {description}"
    _reject_unsupported_number_words((name, description), path)
    if any(
        field in item and item[field] not in (None, "", [], {})
        for field in _CONTAINER_STRUCTURED_CONTENT_FIELDS
    ):
        return {}
    has_empty_state = bool(re.search(r"\bempty\b", combined))
    has_full_state = bool(re.search(r"\b(?:full|filled|loaded)\b", combined))
    if has_empty_state and has_full_state:
        raise CharacterValidationResponseError(
            f"{path} has contradictory ammunition-container state"
        )
    if any(marker in combined for marker in _SPECIAL_AMMUNITION_MARKERS):
        raise CharacterValidationResponseError(
            f"{path} is special ammunition and may not be consolidated"
        )
    source_text_is_pure = all(
        _source_text_is_pure(text, _AMMUNITION_SOURCE_TOKENS)
        for text in (name, description)
    )
    if not source_text_is_pure:
        if any(re.search(r"\bx\b", text) for text in (name, description)):
            raise CharacterValidationResponseError(
                f"{path} contains an unbound ammunition x token"
            )
        return {}

    quantity = _source_quantity(item, f"{path}.quantity")
    amount_token = r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    aliases = sorted(
        {
            alias
            for _canonical, canonical_aliases in _AMMUNITION_NAMES
            for alias in canonical_aliases
        },
        key=len,
        reverse=True,
    )
    alias_pattern = "|".join(re.escape(alias) for alias in aliases)
    text_patterns = (
        re.compile(
            rf"^(?:a |an |the )?(?:(?:bundle|stack|pile) of |"
            rf"(?:quiver|bolt case|case) (?:with|containing) )?"
            rf"({amount_token})\s*(?:(?:standard|ordinary)\s+)?"
            rf"({alias_pattern})(?: pieces?)?\.?$"
        ),
        re.compile(
            rf"^(?:a |an |the )?({alias_pattern})\s*(x|×|:)\s*"
            rf"({amount_token})\.?$"
        ),
    )

    normalized_texts = [
        re.sub(r"\s+", " ", text).strip()
        for text in (name, description)
    ]
    evidence_candidates = []
    matched_amount_spans = {0: set(), 1: set()}
    matched_x_spans = {0: set(), 1: set()}
    for text_index, normalized_text in enumerate(normalized_texts):
        canonical_exact = _canonical_ammunition_name(normalized_text.rstrip("."))
        if canonical_exact is not None:
            explicit_quantity = _explicit_source_quantity(
                item,
                f"{path}.quantity",
            )
            if explicit_quantity is not None:
                evidence_candidates.append({canonical_exact: explicit_quantity})
            continue
        if re.fullmatch(r"(?:a |an |the )?full(?: leather)? quiver\.?", normalized_text):
            evidence_candidates.append({"arrows": 20 * quantity})
            continue
        if re.fullmatch(
            r"(?:a |an |the )?quiver full of arrows\.?",
            normalized_text,
        ):
            evidence_candidates.append({"arrows": 20 * quantity})
            continue
        if re.fullmatch(r"(?:a |an |the )?full(?: leather)? bolt case\.?", normalized_text):
            evidence_candidates.append({"crossbow bolts": 20 * quantity})
            continue
        for pattern_index, pattern in enumerate(text_patterns):
            match = pattern.fullmatch(normalized_text)
            if not match:
                continue
            if pattern_index == 0:
                amount, ammo_name = match.groups()
                amount_group = 1
            else:
                ammo_name, multiplier, amount = match.groups()
                amount_group = 3
                if multiplier == "x":
                    matched_x_spans[text_index].add(match.span(2))
            canonical = _canonical_ammunition_name(ammo_name)
            if canonical is not None:
                parsed_amount = _parse_positive_amount(
                    amount,
                    f"{path}.ammunition",
                )
                evidence_candidates.append({canonical: parsed_amount * quantity})
                matched_amount_spans[text_index].add(match.span(amount_group))
            break

    # A destructive conversion is valid only when every persisted numeric
    # token is part of the exact amount evidence.  Never partially parse a row
    # such as name="10 arrows", description="20 standard arrows" or accept an
    # "empty" container whose prose still carries a count.
    for text_index, normalized_text in enumerate(normalized_texts):
        for match in re.finditer(r"\d[\d,]*", normalized_text):
            if match.span() not in matched_amount_spans[text_index]:
                raise CharacterValidationResponseError(
                    f"{path} contains an ambiguous or unbound ammunition amount"
                )
        for match in re.finditer(r"\bx\b", normalized_text):
            if match.span() not in matched_x_spans[text_index]:
                raise CharacterValidationResponseError(
                    f"{path} contains an unbound ammunition x token"
                )

    if not evidence_candidates:
        return {}
    first = evidence_candidates[0]
    if any(candidate != first for candidate in evidence_candidates[1:]):
        raise CharacterValidationResponseError(
            f"{path} has ambiguous ammunition quantities"
        )
    if has_empty_state:
        raise CharacterValidationResponseError(
            f"{path} has contradictory ammunition-container state"
        )
    return first


def _supported_container_rename(item: Dict[str, Any]) -> Optional[str]:
    """Return the canonical name for a narrowly recognized ammo container."""

    name = re.sub(
        r"\s+",
        " ",
        str(item.get("item_name", "")).casefold().replace("-", " "),
    ).strip()
    description = str(item.get("description", "")).casefold()
    if not all(
        _source_text_is_pure(text, _AMMUNITION_SOURCE_TOKENS)
        for text in (name, description)
    ):
        return None
    for field in _CONTAINER_STRUCTURED_CONTENT_FIELDS:
        if field in item and item[field] not in (None, "", [], {}):
            return None
    for field in _CONTAINER_BOOLEAN_STATE_FIELDS:
        if field in item and type(item[field]) is not bool:
            return None
    for field in _CONTAINER_COUNT_STATE_FIELDS:
        if field in item and (
            type(item[field]) is not int or item[field] < 0
        ):
            return None
    for field in _CONTAINER_TEXT_STATE_FIELDS:
        if field in item and (
            not isinstance(item[field], str)
            or item[field].strip().casefold()
            not in {"empty", "full", "loaded", "filled"}
        ):
            return None

    quiver_name = re.fullmatch(
        r"(?:empty|full) quiver|quiver (?:full of arrows|with \d+ arrows?)",
        name,
    )
    bolt_case_name = re.fullmatch(
        r"(?:empty|full) bolt case|bolt case (?:full of crossbow bolts|with \d+ crossbow bolts?)",
        name,
    )
    description_has_quiver_state = bool(
        re.search(r"\b(?:empty|full)\b.*\bquiver\b", description)
        or re.search(r"\bquiver\b.*\b\d+\s+arrows?\b", description)
    )
    description_has_bolt_case_state = bool(
        re.search(r"\b(?:empty|full)\b.*\bbolt case\b", description)
        or re.search(
            r"\bbolt case\b.*\b\d+\s+crossbow bolts?\b",
            description,
        )
    )
    canonical_name = None
    if quiver_name or (name == "quiver" and description_has_quiver_state):
        canonical_name = "Quiver"
    elif bolt_case_name or (
        name == "bolt case" and description_has_bolt_case_state
    ):
        canonical_name = "Bolt case"
    if canonical_name is None:
        return None

    try:
        evidence = _ammunition_evidence_from_item(item, "container state")
    except CharacterValidationResponseError:
        return None
    evidence_key = "arrows" if canonical_name == "Quiver" else "crossbow bolts"
    evidenced_count = evidence.get(evidence_key, 0)
    relevant_count_field = (
        "arrow_count" if canonical_name == "Quiver" else "bolt_count"
    )
    for field in (relevant_count_field, "ammo_count", "current_load"):
        if field in item and item[field] != evidenced_count:
            return None
    irrelevant_count_field = (
        "bolt_count" if canonical_name == "Quiver" else "arrow_count"
    )
    if item.get(irrelevant_count_field, 0):
        return None
    # Reconcile every persisted state field independently against the same
    # evidenced count.  Using one field as a fallback for another lets
    # contradictory pairs (container_state="full", state="empty") through.
    for field in ("full", "is_full"):
        if field not in item:
            continue
        if item[field] is True and evidenced_count != 20:
            return None
        if item[field] is False and evidenced_count == 20:
            return None
    if "loaded" in item:
        if item["loaded"] is True and evidenced_count <= 0:
            return None
        if item["loaded"] is False and evidenced_count != 0:
            return None
    for field in _CONTAINER_TEXT_STATE_FIELDS:
        if field not in item:
            continue
        state_value = item[field].strip().casefold()
        if state_value == "empty" and evidenced_count != 0:
            return None
        if state_value in {"full", "filled"} and evidenced_count != 20:
            return None
        if state_value == "loaded" and evidenced_count <= 0:
            return None
    return canonical_name


def _consumed_container_update(
    source_item: Dict[str, Any],
    canonical_name: str,
    canonical_description: str,
) -> Dict[str, Any]:
    """Build a non-destructive container update with consumable state cleared."""

    update = {
        "item_name": canonical_name,
        "description": canonical_description,
    }
    for field in _CONTAINER_BOOLEAN_STATE_FIELDS:
        if field in source_item:
            update[field] = False
    for field in _CONTAINER_COUNT_STATE_FIELDS:
        if field in source_item:
            update[field] = 0
    for field in _CONTAINER_TEXT_STATE_FIELDS:
        if field in source_item:
            update[field] = "empty"
    for field in _CONTAINER_STRUCTURED_CONTENT_FIELDS:
        if field in source_item:
            update[field] = copy.deepcopy(source_item[field])
    return update


def _feature_version_signature(value: Any):
    """Return a conservative comparable signature for a versioned feature."""

    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(.*?)\s*\(([^()]*)\)\s*", value)
    if not match:
        return None
    base = re.sub(r"\s+", " ", match.group(1)).strip().casefold()
    version_text = re.sub(r"\s+", " ", match.group(2)).strip().casefold()
    numbers = tuple(int(number) for number in re.findall(r"\d+", version_text))
    if not base or not numbers:
        return None
    template = re.sub(r"\d+", "#", version_text)
    return base, template, numbers


def _strictly_newer_feature(candidate: Any, existing_names: List[Any]) -> bool:
    signature = _feature_version_signature(candidate)
    if signature is None:
        return False
    base, template, numbers = signature
    for other_name in existing_names:
        other = _feature_version_signature(other_name)
        if other is None:
            continue
        other_base, other_template, other_numbers = other
        if (
            other_base == base
            and other_template == template
            and len(other_numbers) == len(numbers)
            and all(new >= old for new, old in zip(other_numbers, numbers))
            and any(new > old for new, old in zip(other_numbers, numbers))
        ):
            return True
    return False


def _aggregate_evidence(
    items: List[Dict[str, Any]],
    extractor,
    path: str,
) -> Dict[str, int]:
    aggregate: Dict[str, int] = {}
    for index, item in enumerate(items):
        evidence = extractor(item, f"{path}[{index}]")
        for key, amount in evidence.items():
            aggregate[key] = aggregate.get(key, 0) + amount
    return aggregate


def _require_exact_conservation(
    kind: str,
    actual: Dict[str, int],
    evidenced: Dict[str, int],
) -> None:
    actual_nonzero = {key: value for key, value in actual.items() if value}
    evidence_nonzero = {key: value for key, value in evidenced.items() if value}
    if actual_nonzero != evidence_nonzero:
        raise CharacterValidationResponseError(
            f"{kind} conservation mismatch: changes={actual_nonzero}, "
            f"removed_source={evidence_nonzero}"
        )


def _load_response_object(ai_response: str, contract_name: str) -> Dict[str, Any]:
    if not isinstance(ai_response, str) or not ai_response.strip():
        raise CharacterValidationResponseError(
            f"{contract_name}: response is empty or non-text"
        )
    start_idx = ai_response.find('{')
    end_idx = ai_response.rfind('}')
    if start_idx < 0 or end_idx < start_idx:
        raise CharacterValidationResponseError(
            f"{contract_name}: no JSON object found"
        )
    try:
        parsed = json.loads(ai_response[start_idx:end_idx + 1])
    except json.JSONDecodeError as exc:
        raise CharacterValidationResponseError(
            f"{contract_name}: invalid JSON: {exc}"
        ) from exc
    if not isinstance(parsed, dict):
        raise CharacterValidationResponseError(
            f"{contract_name}: root must be a JSON object"
        )
    return parsed


def _is_valid_type(value: Any, expected_type: Union[str, list]) -> bool:
    if isinstance(expected_type, list):
        return any(_is_valid_type(value, t) for t in expected_type)

    type_map = {
        "object": dict,
        "dict": dict,
        "array": list,
        "list": list,
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }

    expected_python = type_map.get(expected_type)
    if expected_python is None:
        return True

    if isinstance(expected_python, tuple):
        return isinstance(value, expected_python)
    return isinstance(value, expected_python)


def validate_schema(data: Any, schema: dict, path: str = "root") -> list[str]:
    errors: list[str] = []

    if schema.get("type") and not _is_valid_type(data, schema["type"]):
        errors.append(f"{path}: expected type {schema['type']}, got {type(data).__name__}")

    if not isinstance(data, dict):
        return errors

    for field in schema.get("required", []):
        if field not in data:
            errors.append(f"{path}: missing required field '{field}'")

    for field, subschema in schema.get("properties", {}).items():
        if field in data:
            nested = data[field]
            errors.extend(validate_schema(nested, subschema, f"{path}.{field}"))

    return errors

# Import OpenAI usage tracking (safe - won't break if fails)
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass
import config
from utils.file_operations import safe_read_json, safe_write_json
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

class AICharacterValidator:
    def __init__(self):
        """Initialize AI-powered validator with caching"""
        self.logger = logging.getLogger(__name__)
        self.corrections_made = []
        
        # Load prompts from external files
        self.ac_prompt = self._load_prompt('character_validator_ac.txt')
        self.inventory_prompt = self._load_prompt('character_validator_inventory.txt')
        
        # Initialize validation cache
        self.cache_file = os.path.join('modules', 'validation_cache.json')
        self.validation_cache = self._load_cache()
    
    def _load_prompt(self, filename: str) -> str:
        """
        Load a prompt from an external file
        
        Args:
            filename: Name of the prompt file
            
        Returns:
            Content of the prompt file
        """
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'prompts', filename)
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
                debug(f"Loaded prompt from {filename}: {len(prompt)} characters", category="character_validation")
                return prompt
        except FileNotFoundError:
            error(f"Prompt file not found: {prompt_path}", category="character_validation")
            # Fall back to empty prompt if file not found
            return ""
        except Exception as e:
            error(f"Error loading prompt from {filename}: {str(e)}", category="character_validation")
            return ""
    
    def extract_ac_relevant_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only the fields relevant for AC validation.
        This dramatically reduces token usage from ~7800 to ~500-800.
        
        Based on Gemini consultation, includes all D&D 5e AC-affecting fields:
        - Core context (class, race) for AC rules
        - All ability scores needed for Unarmored Defense
        - Equipment effects array with structured AC data
        - Racial traits and feats that could affect AC
        - Armor proficiencies for validation
        
        Args:
            character_data: Full character JSON data
            
        Returns:
            Minimal data needed for AC validation
        """
        # Start with essential fields including class and race for context
        ac_data = {
            'name': character_data.get('name', 'Unknown'),
            'armorClass': character_data.get('armorClass', 10),
            # Hash provenance must distinguish a repaired/default value from an
            # explicitly persisted value. The marker is read-only model context.
            '_armorClass_present': 'armorClass' in character_data,
            'class': character_data.get('class', 'Unknown'),  # Critical for Unarmored Defense rules
            'race': character_data.get('race', 'Unknown'),    # Critical for natural armor (Tortle, etc.)
            'abilities': {
                'dexterity': character_data.get('abilities', {}).get('dexterity', 10),
                'constitution': character_data.get('abilities', {}).get('constitution', 10),  # Barbarian Unarmored Defense
                'wisdom': character_data.get('abilities', {}).get('wisdom', 10)  # Monk Unarmored Defense
            }
        }
        
        # Include armor proficiencies to validate proper armor usage
        proficiencies = character_data.get('proficiencies', {})
        if 'armor' in proficiencies:
            ac_data['proficiencies'] = {'armor': proficiencies['armor']}
        
        # Process equipment_effects array - HIGH PRIORITY (structured AC data)
        equipment_effects = character_data.get('equipment_effects', [])
        ac_equipment_effects = []
        for effect in equipment_effects:
            # Include effects that explicitly target AC
            if effect.get('target', '').upper() == 'AC' or 'ac' in effect.get('target', '').lower():
                ac_equipment_effects.append(effect)
        
        if ac_equipment_effects:
            ac_data['equipment_effects'] = ac_equipment_effects
        
        # Filter equipment to only AC-relevant items (refined logic)
        equipment = character_data.get('equipment', [])
        ac_relevant_equipment = []
        
        for item in equipment:
            item_name = item.get('item_name', '').lower()
            item_type = item.get('item_type', '').lower()
            description = item.get('description', '').lower()
            equipped = item.get('equipped', False)
            
            # Include if it's armor, shield, or potentially magical AC item
            include_item = False
            
            # Always include armor and shields
            if item_type == 'armor' or 'armor' in item_name or 'shield' in item_name:
                include_item = True
            
            # Check for explicit AC bonuses in item fields
            elif 'ac_base' in item or 'ac_bonus' in item:
                include_item = True
            
            # Include equipped items with specific AC patterns in description
            elif equipped:
                # Look for explicit AC bonuses like "+1 to AC", "bonus to AC"
                if any(pattern in description for pattern in ['+1 to ac', '+2 to ac', 'bonus to ac', 'armor class']):
                    include_item = True
                # Check known AC-boosting item names
                elif any(ac_item in item_name for ac_item in ['ring of protection', 'cloak of protection', 'bracers of defense']):
                    include_item = True
            
            if include_item:
                # Include all armor-related fields for proper validation
                item_data = {
                    'item_name': item.get('item_name'),
                    'item_type': item.get('item_type'),
                    'equipped': item.get('equipped', False),
                    'description': item.get('description', '')[:200]  # Limit description length
                }
                
                # Include armor-specific fields if present
                for field in ['ac_base', 'ac_bonus', 'dex_limit', 'armor_category', 'stealth_disadvantage']:
                    if field in item:
                        item_data[field] = item[field]
                
                ac_relevant_equipment.append(item_data)
        
        ac_data['equipment'] = ac_relevant_equipment
        
        # Include class features that might affect AC (like Defense fighting style, Unarmored Defense)
        class_features = character_data.get('classFeatures', [])
        ac_relevant_features = []
        
        for feature in class_features:
            feature_name = feature.get('name', '').lower()
            feature_desc = feature.get('description', '').lower()
            # Expanded keywords to catch Unarmored Defense and other AC features
            if any(keyword in feature_name for keyword in ['defense', 'armor', 'ac', 'protection', 'shield', 'unarmored']):
                ac_relevant_features.append(feature)
            # Also check description for AC mentions
            elif any(keyword in feature_desc for keyword in ['armor class', 'ac equal', 'ac bonus']):
                ac_relevant_features.append(feature)
        
        if ac_relevant_features:
            ac_data['classFeatures'] = ac_relevant_features
        
        # Include racial traits (for natural armor like Tortle)
        racial_traits = character_data.get('racialTraits', [])
        ac_relevant_traits = []
        
        for trait in racial_traits:
            trait_name = trait.get('name', '').lower()
            trait_desc = trait.get('description', '').lower()
            if any(keyword in trait_name + trait_desc for keyword in ['armor', 'ac', 'natural armor', 'protection']):
                ac_relevant_traits.append(trait)
        
        if ac_relevant_traits:
            ac_data['racialTraits'] = ac_relevant_traits
        
        # Include feats (for Defensive Duelist, Medium Armor Master, etc.)
        feats = character_data.get('feats', [])
        ac_relevant_feats = []
        
        for feat in feats:
            # If feat is a string, check the name
            if isinstance(feat, str):
                feat_lower = feat.lower()
                if any(keyword in feat_lower for keyword in ['defense', 'armor', 'ac', 'duelist']):
                    ac_relevant_feats.append(feat)
            # If feat is a dict, check name and description
            elif isinstance(feat, dict):
                feat_name = feat.get('name', '').lower()
                feat_desc = feat.get('description', '').lower()
                if any(keyword in feat_name + feat_desc for keyword in ['defense', 'armor', 'ac', 'duelist']):
                    ac_relevant_feats.append(feat)
        
        if ac_relevant_feats:
            ac_data['feats'] = ac_relevant_feats
        
        # Include active effects if present (mage armor, shield spell, etc.)
        active_effects = character_data.get('activeEffects', [])
        if active_effects:
            ac_data['activeEffects'] = active_effects
        
        # Log the reduction
        original_size = len(json.dumps(character_data))
        reduced_size = len(json.dumps(ac_data))
        reduction_pct = (1 - reduced_size/original_size) * 100
        
        debug(f"[AC Extraction] Reduced data from {original_size:,} to {reduced_size:,} chars ({reduction_pct:.1f}% reduction)", category="character_validation")
        debug(f"[AC Extraction] Equipment: {len(equipment)} -> {len(ac_relevant_equipment)} items", category="character_validation")
        debug(f"[AC Extraction] Equipment effects: {len(equipment_effects)} -> {len(ac_equipment_effects)} AC-relevant", category="character_validation")
        debug(f"[AC Extraction] Included: {len(ac_relevant_features)} class features, {len(ac_relevant_traits)} racial traits, {len(ac_relevant_feats)} feats", category="character_validation")
        
        return ac_data
    
    def extract_inventory_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only inventory-relevant data for validation.
        Focus on items that commonly have categorization issues.
        
        Based on Gemini consultation:
        - Check equipment items that might be miscategorized as miscellaneous
        - Exclude high-confidence miscellaneous items
        - Include ambiguous items like scrolls regardless of type
        
        Args:
            character_data: Full character JSON data
            
        Returns:
            Minimal data needed for inventory validation
        """
        inventory_data = {
            'name': character_data.get('name', 'Unknown'),
            'equipment': []
        }
        
        equipment = character_data.get('equipment', [])
        
        # Filter to items most likely to need validation
        for item in equipment:
            item_name = item.get('item_name', '').lower()
            item_type = item.get('item_type', '').lower()
            description = item.get('description', '').lower()
            
            include = False
            
            # 1. Check miscellaneous items (but exclude high-confidence ones)
            if item_type == 'miscellaneous':
                # Exclude items that are almost certainly correct miscellaneous
                high_confidence_misc = ['gemstone', 'coin', 'gold', 'silver', 'copper', 
                                       'signet', 'deed', 'letter', 'page', 'parchment',
                                       'medallion', 'brooch', 'locket', 'chalice', 'goblet',
                                       'crown', 'ingot', 'relic']
                
                # Don't validate if it's a high-confidence miscellaneous item
                if not any(keyword in item_name for keyword in high_confidence_misc):
                    # But DO include if it might be something else
                    if any(keyword in item_name for keyword in ['arrow', 'bolt', 'bullet', 'dart']):
                        include = True  # Likely ammunition
                    elif any(keyword in item_name for keyword in ['ration', 'food', 'bread', 'meat', 'potion', 'scroll', 'elixir']):
                        include = True  # Likely consumable
                    elif any(keyword in item_name for keyword in ['torch', 'rope', 'tools', 'kit', 'pack', 'bedroll', 'tent']):
                        include = True  # Likely equipment
                    else:
                        # Include other miscellaneous for review (but not high-confidence ones)
                        include = True
            
            # 2. Check equipment items that might be miscellaneous (rings, amulets, etc)
            elif item_type == 'equipment':
                # These are often miscategorized as equipment when they should be miscellaneous
                if any(keyword in item_name for keyword in ['ring', 'amulet', 'talisman', 'symbol', 'pendant', 'necklace']):
                    include = True  # Often should be miscellaneous
                # Check for scrolls which are ambiguous
                elif 'scroll' in item_name:
                    include = True  # Could be consumable or equipment
                # Include items with special/magical effects that might be miscellaneous
                elif any(keyword in description for keyword in ['summon', 'magical', 'enchanted', 'artifact']):
                    include = True  # Might be miscellaneous
            
            # 3. Check weapons that might be ammunition
            elif item_type == 'weapon' and any(keyword in item_name for keyword in ['arrow', 'bolt', 'bullet', 'dart']):
                include = True  # Ammunition miscategorized as weapon
            
            # 4. Check for consumables miscategorized as other types
            elif item_type != 'consumable' and any(keyword in item_name for keyword in ['potion', 'elixir', 'ration', 'food', 'water', 'ale', 'wine']):
                include = True  # Should be consumable
            
            # 5. Check for equipment miscategorized as other types  
            elif item_type != 'equipment' and any(keyword in item_name for keyword in ['rope', 'torch', 'lantern', 'tools', 'kit', 'pack', 'bedroll', 'tent', 'map']):
                include = True  # Should be equipment
            
            # 6. Always check items with "scroll" regardless of current type (ambiguous)
            elif 'scroll' in item_name:
                include = True  # Scrolls are ambiguous - could be consumable or equipment/misc
            
            if include:
                # Only include necessary fields
                inventory_data['equipment'].append({
                    'item_name': item.get('item_name'),
                    'item_type': item.get('item_type'),
                    'description': item.get('description', '')[:150],  # Slightly longer for context
                    'quantity': item.get('quantity', 1)
                })
        
        # Log the reduction
        original_count = len(equipment)
        filtered_count = len(inventory_data['equipment'])
        
        debug(f"[Inventory Extraction] Filtered items from {original_count} to {filtered_count} for validation", category="character_validation")
        
        return inventory_data
    
    def extract_currency_consolidation_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only items relevant for currency and ammunition consolidation.
        Focus on items that might be loose coins or ammunition to consolidate.
        
        Enhanced based on Gemini consultation:
        - Expanded exclusion list for false positives
        - Added locked/sealed container detection
        - Improved container keywords
        - Consolidated ammunition checks
        
        Args:
            character_data: Full character JSON data
            
        Returns:
            Minimal data needed for consolidation validation
        """
        consolidation_data = {
            'name': character_data.get('name', 'Unknown'),
            'currency': character_data.get('currency', {}),
            'ammunition': character_data.get('ammunition', []),
            'equipment': []
        }
        
        equipment = character_data.get('equipment', [])

        # Only send candidates the deterministic parser could prove safe. This
        # avoids spending a provider call on mixed/ambiguous inventory and makes
        # a consumed canonical container disappear from fresh-cache replays.
        for item in equipment:
            if not isinstance(item, dict):
                continue
            # The prompt builder exposes only the four fields it needs, while
            # the parser retains this complete private source row so a safe
            # container rename cannot discard unrelated item metadata.
            candidate = copy.deepcopy(item)
            try:
                supported_rename = _supported_container_rename(candidate)
                destructive_evidence = False
                if supported_rename is None:
                    _require_destructively_safe_source_item(
                        candidate,
                        "T054 extraction",
                    )
                    destructive_evidence = bool(
                        _currency_evidence_from_item(candidate, "T054 extraction")
                        or _ammunition_evidence_from_item(candidate, "T054 extraction")
                    )
                include = bool(supported_rename or destructive_evidence)
            except CharacterValidationResponseError:
                include = False
            if include:
                consolidation_data['equipment'].append(candidate)
        
        # Log the reduction
        original_count = len(equipment)
        filtered_count = len(consolidation_data['equipment'])
        
        debug(f"[Currency Extraction] Filtered items from {original_count} to {filtered_count} for consolidation", category="character_validation")
        
        return consolidation_data
    
    def _load_cache(self) -> Dict[str, Any]:
        """
        Load validation cache from file
        
        Returns:
            Cache dictionary or empty dict if not found
        """
        if os.path.exists(self.cache_file):
            cache = safe_read_json(self.cache_file)
            if cache:
                debug(f"[Validation Cache] Loaded cache with {len(cache)} entries", category="character_validation")
                return cache
        return {}
    
    def _save_cache(self):
        """Save validation cache to file"""
        try:
            safe_write_json(self.cache_file, self.validation_cache)
            debug(f"[Validation Cache] Saved cache with {len(self.validation_cache)} entries", category="character_validation")
        except Exception as e:
            error(f"Failed to save validation cache: {str(e)}", category="character_validation")
    
    def _compute_ac_hash(self, ac_data: Dict[str, Any]) -> str:
        """
        Compute a hash of AC-relevant data for caching
        
        Args:
            ac_data: AC-relevant data extracted from character
            
        Returns:
            SHA-256 hash of the data
        """
        # Create a stable JSON representation for hashing
        json_str = json.dumps(ac_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _is_ac_validation_cached(self, character_name: str, ac_hash: str) -> bool:
        """
        Check if AC validation is cached and still valid
        
        Args:
            character_name: Name of the character
            ac_hash: Hash of current AC-relevant data
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if AC data has changed
        if cache_entry.get('ac_hash') != ac_hash:
            debug(f"[Validation Cache] AC data changed for {character_name}", category="character_validation")
            return False
        
        # Check if cache is still fresh (optional: add time-based expiry)
        # For now, we'll keep cache valid indefinitely until data changes
        
        debug(f"[Validation Cache] Using cached AC validation for {character_name}", category="character_validation")
        return True
    
    def _update_ac_cache(self, character_name: str, ac_hash: str, validated_data: Dict[str, Any]):
        """
        Update cache with new AC validation results
        
        Args:
            character_name: Name of the character
            ac_hash: Hash of AC-relevant data
            validated_data: Validated character data
        """
        if character_name not in self.validation_cache:
            self.validation_cache[character_name] = {}
        
        self.validation_cache[character_name].update({
            'ac_hash': ac_hash,
            'last_ac_validation': datetime.now().isoformat(),
            'ac_value': validated_data.get('armorClass', 10)
        })
        
        self._save_cache()
        debug(f"[Validation Cache] Updated AC cache for {character_name}", category="character_validation")
    
    def _compute_inventory_hash(self, inventory_data: Dict[str, Any]) -> str:
        """
        Compute a hash of inventory data for caching
        
        Args:
            inventory_data: Inventory-relevant data extracted from character
            
        Returns:
            SHA-256 hash of the data
        """
        # Create a stable JSON representation for hashing
        json_str = json.dumps(inventory_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _is_inventory_validation_cached(self, character_name: str, inventory_hash: str) -> bool:
        """
        Check if inventory validation is cached and still valid
        
        Args:
            character_name: Name of the character
            inventory_hash: Hash of current inventory data
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if inventory data has changed
        if cache_entry.get('inventory_hash') != inventory_hash:
            debug(f"[Validation Cache] Inventory data changed for {character_name}", category="character_validation")
            return False
        
        debug(f"[Validation Cache] Using cached inventory validation for {character_name}", category="character_validation")
        return True
    
    def _update_inventory_cache(self, character_name: str, inventory_hash: str):
        """
        Update cache with new inventory validation results
        
        Args:
            character_name: Name of the character
            inventory_hash: Hash of inventory data
        """
        if character_name not in self.validation_cache:
            self.validation_cache[character_name] = {}
        
        self.validation_cache[character_name].update({
            'inventory_hash': inventory_hash,
            'last_inventory_validation': datetime.now().isoformat()
        })
        
        self._save_cache()
        debug(f"[Validation Cache] Updated inventory cache for {character_name}", category="character_validation")
    
    def _compute_currency_hash(self, consolidation_data: Dict[str, Any]) -> str:
        """
        Compute a hash of currency consolidation data for caching
        
        Args:
            consolidation_data: Currency-relevant data extracted from character
            
        Returns:
            SHA-256 hash of the data
        """
        # Create a stable JSON representation for hashing
        json_str = json.dumps(consolidation_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def _is_currency_validation_cached(self, character_name: str, currency_hash: str) -> bool:
        """
        Check if currency consolidation is cached and still valid
        
        Args:
            character_name: Name of the character
            currency_hash: Hash of current currency consolidation data
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if currency data has changed
        if cache_entry.get('currency_hash') != currency_hash:
            debug(f"[Validation Cache] Currency data changed for {character_name}", category="character_validation")
            return False
        
        debug(f"[Validation Cache] Using cached currency consolidation for {character_name}", category="character_validation")
        return True
    
    def _update_currency_cache(self, character_name: str, currency_hash: str):
        """
        Update cache with new currency consolidation results
        
        Args:
            character_name: Name of the character
            currency_hash: Hash of currency consolidation data
        """
        if character_name not in self.validation_cache:
            self.validation_cache[character_name] = {}
        
        self.validation_cache[character_name].update({
            'currency_hash': currency_hash,
            'last_currency_validation': datetime.now().isoformat()
        })
        
        self._save_cache()
        debug(f"[Validation Cache] Updated currency cache for {character_name}", category="character_validation")
        
    def _apply_deterministic_validations(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run non-provider repairs without ever mutating the caller's object."""

        corrected_data = copy.deepcopy(character_data)
        corrected_data, contract_repairs = repair_required_ammunition_field(
            corrected_data
        )
        for repair in contract_repairs:
            correction = f"Repaired character contract: {repair}"
            if correction not in self.corrections_made:
                self.corrections_made.append(correction)
        corrected_data = self.validate_status_condition_consistency(corrected_data)
        corrected_data = self.ensure_currency_integrity(corrected_data)
        corrected_data = self.consolidate_ammunition(corrected_data)
        return corrected_data

    def validate_and_correct_character_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        AI-powered validation and correction of character data
        
        Args:
            character_data: Character JSON data
            
        Returns:
            AI-corrected character data with proper AC calculation
        """
        self.corrections_made = []
        
        # Log activation message for user visibility in debug window
        character_name = character_data.get('name', 'Unknown')
        # Use print for immediate visibility in debug tab
        print(f"DEBUG: [AI Validator] Activating character validator for {character_name}...")
        info(f"[AI Validator] Activating character validator for {character_name}...", category="character_validation")
        
        # Keep an untouched snapshot. Provider work and deterministic repairs
        # always operate on copies so outcome comparison remains authoritative.
        original_snapshot = copy.deepcopy(character_data)

        # OPTIMIZATION: Batch all validations into a single AI call
        ai_result = self.ai_validate_all_batched_with_result(
            copy.deepcopy(original_snapshot)
        )
        if not ai_result.success:
            warning(
                f"[AI Validator] Character validation failed for {character_name}: "
                f"{ai_result.error}",
                category="character_validation",
            )
            corrected_data = self._apply_deterministic_validations(
                original_snapshot
            )
            return _failed_validation_result(
                character_data,
                RuntimeError(ai_result.error or "T053 validation failed"),
                corrected_data,
            )
        corrected_data = self._apply_deterministic_validations(ai_result.data)
        
        # Future: Add other AI validations here
        # - Temporary effects expiration  
        # - Attack bonus calculation
        # - Saving throw bonuses
        
        # Log completion message
        if self.corrections_made:
            print(f"DEBUG: [AI Validator] Character validation complete for {character_name}: {len(self.corrections_made)} corrections made")
            info(f"[AI Validator] Character validation complete for {character_name}: {len(self.corrections_made)} corrections made", category="character_validation")
            for correction in self.corrections_made:
                print(f"DEBUG:   - {correction}")
                info(f"  - {correction}", category="character_validation")
        else:
            print(f"DEBUG: [AI Validator] Character validation complete for {character_name}: No corrections needed")
            info(f"[AI Validator] Character validation complete for {character_name}: No corrections needed", category="character_validation")
        
        return _validation_result(character_data, corrected_data)

    def validate_and_correct_character(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Backward-compatible data-only facade for full validation."""

        return self.validate_and_correct_character_with_result(character_data).data
    
    def check_validation_needs(self, character_data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check which validations actually need API calls (not cached)
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Dictionary indicating which validations need API calls
        """
        character_name = character_data.get('name', 'Unknown')
        needs_validation = {
            'ac': False,
            'inventory': False,
            'currency': False,
            'class_features': False  # Always validate for now (no caching yet)
        }
        
        # Extract data for each validator
        ac_data = self.extract_ac_relevant_data(character_data)
        ac_hash = self._compute_ac_hash(ac_data)
        
        inventory_data = self.extract_inventory_data(character_data)
        inventory_hash = self._compute_inventory_hash(inventory_data)
        
        currency_data = self.extract_currency_consolidation_data(character_data)
        currency_hash = self._compute_currency_hash(currency_data)
        
        # Check cache for each
        if not self._is_ac_validation_cached(character_name, ac_hash):
            needs_validation['ac'] = True
            debug(f"[Smart Batch] {character_name} needs AC validation", category="character_validation")
        
        if len(inventory_data['equipment']) > 0 and not self._is_inventory_validation_cached(character_name, inventory_hash):
            needs_validation['inventory'] = True
            debug(f"[Smart Batch] {character_name} needs inventory validation", category="character_validation")
        
        if len(currency_data['equipment']) > 0 and not self._is_currency_validation_cached(character_name, currency_hash):
            needs_validation['currency'] = True
            debug(f"[Smart Batch] {character_name} needs currency validation", category="character_validation")
        
        # Class features don't have caching yet, always validate if batched
        needs_validation['class_features'] = False  # Disable for now unless specifically needed
        
        return needs_validation
    
    def validate_and_correct_character_smart_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        Smart validation that only calls validators that need updates

        Args:
            character_data: Character JSON data

        Returns:
            AI-corrected character data
        """
        character_name = character_data.get('name', 'Unknown')
        info(f"[Smart Validator] Checking {character_name} for needed validations...", category="character_validation")
        original_snapshot = copy.deepcopy(character_data)

        # Check what needs validation
        needs = self.check_validation_needs(original_snapshot)

        # Count how many validations are needed
        needed_count = sum(1 for v in needs.values() if v)

        if needed_count == 0:
            print(f"DEBUG: [Smart Validator] {character_name} - All validations cached, skipping API calls")
            info(f"[Smart Validator] {character_name} - All validations cached, skipping API calls", category="character_validation")
        else:
            print(f"DEBUG: [Smart Validator] {character_name} needs {needed_count} validation(s)")
            info(f"[Smart Validator] {character_name} needs {needed_count} validation(s)", category="character_validation")
        
        # Apply only needed validations
        corrected_data = copy.deepcopy(original_snapshot)
        corrections_before = copy.deepcopy(self.corrections_made)

        def failed_after_deterministic(result, task_id):
            self.corrections_made = corrections_before
            repaired_data = self._apply_deterministic_validations(
                original_snapshot
            )
            return _failed_validation_result(
                character_data,
                RuntimeError(f"{task_id} failed: {result.error}"),
                repaired_data,
            )

        if needs['ac']:
            result = self.ai_validate_armor_class_with_result(corrected_data)
            if not result.success:
                return failed_after_deterministic(result, "T051")
            corrected_data = result.data
        
        if needs['inventory']:
            result = self.ai_validate_inventory_categories_with_result(corrected_data)
            if not result.success:
                return failed_after_deterministic(result, "T052")
            corrected_data = result.data
        
        if needs['currency']:
            result = self.ai_consolidate_inventory_with_result(corrected_data)
            if not result.success:
                return failed_after_deterministic(result, "T054")
            corrected_data = result.data

        corrected_data = self._apply_deterministic_validations(corrected_data)
        
        return _validation_result(character_data, corrected_data)

    def validate_and_correct_character_smart(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Backward-compatible data-only facade for smart validation."""

        return self.validate_and_correct_character_smart_with_result(character_data).data
    
    def validate_multiple_characters_smart(self, character_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate multiple characters with smart batching based on cache status
        Only creates batches for validators that need API calls
        
        Args:
            character_list: List of character data dictionaries
            
        Returns:
            List of validated character data
        """
        if not character_list:
            return []

        # The legacy batch facade predates explicit validation results, but it
        # must still honor the same ownership rule as the single-character
        # paths: never let deterministic repairs mutate caller-owned objects.
        working_characters = copy.deepcopy(character_list)
        
        info(f"[Smart Batch] Processing {len(working_characters)} characters", category="character_validation")
        
        # Group characters by validation needs
        validation_batches = {
            'ac': [],
            'inventory': [],
            'currency': []
        }
        
        # Track which characters need which validations
        character_needs = {}
        
        for character in working_characters:
            char_name = character.get('name', 'Unknown')
            needs = self.check_validation_needs(character)
            character_needs[char_name] = needs
            
            # Add to appropriate batches
            if needs['ac']:
                validation_batches['ac'].append(character)
            if needs['inventory']:
                validation_batches['inventory'].append(character)
            if needs['currency']:
                validation_batches['currency'].append(character)
        
        # Report batch sizes
        info(f"[Smart Batch] AC batch: {len(validation_batches['ac'])} characters", category="character_validation")
        info(f"[Smart Batch] Inventory batch: {len(validation_batches['inventory'])} characters", category="character_validation")
        info(f"[Smart Batch] Currency batch: {len(validation_batches['currency'])} characters", category="character_validation")
        
        # Process batches (could be parallelized in future)
        results = {}
        
        # Batch AC validations
        if validation_batches['ac']:
            info(f"[Smart Batch] Processing AC validations for {len(validation_batches['ac'])} characters", category="character_validation")
            for character in validation_batches['ac']:
                char_name = character.get('name', 'Unknown')
                validated = self.ai_validate_armor_class(character)
                results[char_name] = validated
        
        # Batch inventory validations
        if validation_batches['inventory']:
            info(f"[Smart Batch] Processing inventory validations for {len(validation_batches['inventory'])} characters", category="character_validation")
            for character in validation_batches['inventory']:
                char_name = character.get('name', 'Unknown')
                # Use existing result if already validated, otherwise use original
                base_data = results.get(char_name, character)
                validated = self.ai_validate_inventory_categories(base_data)
                results[char_name] = validated
        
        # Batch currency validations
        if validation_batches['currency']:
            info(f"[Smart Batch] Processing currency validations for {len(validation_batches['currency'])} characters", category="character_validation")
            for character in validation_batches['currency']:
                char_name = character.get('name', 'Unknown')
                # Use existing result if already validated, otherwise use original
                base_data = results.get(char_name, character)
                validated = self.ai_consolidate_inventory(base_data)
                results[char_name] = validated
        
        # Apply non-AI validations to all characters
        final_results = []
        for character in working_characters:
            char_name = character.get('name', 'Unknown')
            
            # Use validated version if exists, otherwise original
            char_data = results.get(char_name, character)
            
            # Always apply non-AI validations on an owned copy.
            char_data = self._apply_deterministic_validations(char_data)
            
            final_results.append(char_data)
        
        # Report savings
        total_possible = len(working_characters) * 3  # 3 validators per character
        total_called = len(validation_batches['ac']) + len(validation_batches['inventory']) + len(validation_batches['currency'])
        total_skipped = total_possible - total_called
        
        print(f"DEBUG: [Smart Batch] Complete: {total_called}/{total_possible} API calls made ({total_skipped} skipped due to caching)")
        info(f"[Smart Batch] Complete: {total_called}/{total_possible} API calls made ({total_skipped} skipped due to caching)", category="character_validation")
        
        return final_results
    
    def ai_validate_armor_class_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        Use AI to validate and correct Armor Class calculation with caching
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with AI-corrected AC (from cache if unchanged)
        """
        
        # Extract only AC-relevant data to reduce tokens
        ac_relevant_data = self.extract_ac_relevant_data(character_data)
        
        # Compute hash of AC-relevant data
        character_name = character_data.get('name', 'Unknown')
        ac_hash = self._compute_ac_hash(ac_relevant_data)
        
        # Check if validation is cached and unchanged
        if self._is_ac_validation_cached(character_name, ac_hash):
            # Return original data - no changes needed since cached validation passed
            print(f"DEBUG: [Validation Cache] Skipping AC validation for {character_name} - data unchanged")
            info(f"[Validation Cache] Skipping AC validation for {character_name} - data unchanged", category="character_validation")
            
            # Log cache hit statistics
            if character_name in self.validation_cache:
                cache_entry = self.validation_cache[character_name]
                debug(f"[Validation Cache] Last validated: {cache_entry.get('last_ac_validation')}", category="character_validation")
                debug(f"[Validation Cache] Cached AC value: {cache_entry.get('ac_value')}", category="character_validation")
            
            return CharacterValidationResult(
                character_data,
                CharacterValidationStatus.NO_CHANGE,
            )
        
        # Data has changed or not cached - perform validation
        print(f"DEBUG: [Validation Cache] Running AC validation for {character_name} - new/changed data")
        info(f"[Validation Cache] Running AC validation for {character_name} - new/changed data", category="character_validation")
        provider_ac_data = copy.deepcopy(ac_relevant_data)
        provider_ac_data.pop('_armorClass_present', None)
        validation_prompt = self.build_ac_validation_prompt(provider_ac_data)

        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            validator_config = config.CHAR_VALIDATOR_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            validator_config = config.CHAR_VALIDATOR_T051_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            validator_config = config.CHAR_VALIDATOR_LMSTUDIO
        else:  # legacy
            validator_config = config.CHAR_VALIDATOR_LEGACY

        corrections_before = copy.deepcopy(self.corrections_made)
        messages = [
            {"role": "system", "content": self.get_validator_system_prompt()},
            {"role": "user", "content": validation_prompt},
        ]
        max_attempts = 3
        last_error: BaseException = RuntimeError("T051 validation attempts exhausted")
        for attempt in range(1, max_attempts + 1):
            ai_response = None
            try:
                response = capture_and_fanout("T051", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=messages,
                    model=validator_config["model"],
                    temperature=0.1,
                    **{k: v for k, v in validator_config.items() if k != "model"})

                # Track usage if available
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_data'})
                    except:
                        pass

                ai_response = response.choices[0].message.content.strip()

                # Parse AI response to get corrected character data
                corrected_data = self.parse_ai_validation_response(
                    ai_response,
                    provider_ac_data,
                )

                # CRITICAL FIX: Merge the corrections into original data, don't replace!
                # The AI only returns the extracted subset with corrections
                # We need to merge those corrections back into the full character data
                from updates.update_character_info import deep_merge_dict
                merged_data = deep_merge_dict(character_data, corrected_data)

                # Cache the fully merged output, never the pre-correction input. If a
                # later persistence step fails, the unchanged disk data will not hit
                # this entry and validation will self-heal on the next pass.
                final_ac_hash = self._compute_ac_hash(
                    self.extract_ac_relevant_data(merged_data)
                )
                self._update_ac_cache(character_name, final_ac_hash, merged_data)

                return _validation_result(character_data, merged_data)
            except Exception as e:
                last_error = e
                self.corrections_made = copy.deepcopy(corrections_before)
                self.logger.error(
                    f"AI validation failed (attempt {attempt}/{max_attempts}): {e}"
                )
                if attempt < max_attempts and ai_response is not None:
                    messages.extend([
                        {"role": "assistant", "content": ai_response},
                        {
                            "role": "user",
                            "content": (
                                f"VALIDATION ERROR: {e}. Return the complete JSON "
                                "object again. Ensure validated_character_data.armorClass "
                                "exactly equals ac_calculation_breakdown.total_ac and that "
                                "corrections_made accurately describes any changed value."
                            ),
                        },
                    ])

        return _failed_validation_result(character_data, last_error)

    def ai_validate_armor_class(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible data-only facade for T051."""

        return self.ai_validate_armor_class_with_result(character_data).data
    
    def ai_validate_inventory_categories_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        Use AI to validate and correct inventory item categorization with caching
        Following the main character updater pattern: return only changes, use deep merge
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with AI-corrected inventory categories (from cache if unchanged)
        """
        
        # Extract only inventory data that needs validation
        inventory_data = self.extract_inventory_data(character_data)
        
        # Compute hash of inventory data
        character_name = character_data.get('name', 'Unknown')
        inventory_hash = self._compute_inventory_hash(inventory_data)
        
        # Check if validation is cached and unchanged
        if self._is_inventory_validation_cached(character_name, inventory_hash):
            # Return original data - no changes needed since cached validation passed
            print(f"DEBUG: [Validation Cache] Skipping inventory validation for {character_name} - data unchanged")
            info(f"[Validation Cache] Skipping inventory validation for {character_name} - data unchanged", category="character_validation")
            
            # Log cache hit statistics
            if character_name in self.validation_cache:
                cache_entry = self.validation_cache[character_name]
                debug(f"[Validation Cache] Last validated: {cache_entry.get('last_inventory_validation')}", category="character_validation")
            
            return CharacterValidationResult(
                character_data,
                CharacterValidationStatus.NO_CHANGE,
            )
        
        # If no items need validation, skip API call
        if len(inventory_data['equipment']) == 0:
            print(f"DEBUG: [Inventory Validation] No suspicious items found for {character_name} - skipping validation")
            info(f"[Inventory Validation] No suspicious items found for {character_name} - skipping validation", category="character_validation")
            # Update cache to avoid checking again
            self._update_inventory_cache(character_name, inventory_hash)
            return CharacterValidationResult(
                character_data,
                CharacterValidationStatus.NO_CHANGE,
            )
        
        # Data has changed or not cached - perform validation
        print(f"DEBUG: [Validation Cache] Running inventory validation for {character_name} - {len(inventory_data['equipment'])} items to check")
        info(f"[Validation Cache] Running inventory validation for {character_name} - {len(inventory_data['equipment'])} items to check", category="character_validation")
        
        max_attempts = 3
        attempt = 1
        corrections_before = copy.deepcopy(self.corrections_made)
        
        while attempt <= max_attempts:
            try:
                # Build prompt with filtered inventory data
                validation_prompt = self.build_inventory_validation_prompt(inventory_data)

                # Select model config per provider
                from model_config import MODEL_PROVIDER
                if MODEL_PROVIDER == "openai":
                    inv_config = config.CHAR_VALIDATOR_GPT52_NONE
                elif MODEL_PROVIDER == "gemini":
                    inv_config = config.CHAR_VALIDATOR_T052_GEMINI_FLASH_LOW
                elif MODEL_PROVIDER == "lmstudio":
                    inv_config = config.CHAR_VALIDATOR_LMSTUDIO
                else:  # legacy
                    inv_config = config.CHAR_VALIDATOR_LEGACY

                response = capture_and_fanout("T052", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": self.get_inventory_validator_system_prompt()},
                        {"role": "user", "content": validation_prompt}
                    ],
                    model=inv_config["model"],
                    temperature=0.1,
                    **{k: v for k, v in inv_config.items() if k != "model"})
                
                # Track usage if available
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_effects'})
                    except:
                        pass
                
                ai_response = response.choices[0].message.content.strip()
                
                # Parse AI response to get inventory updates only
                inventory_updates = self.parse_inventory_validation_response(
                    ai_response,
                    inventory_data,
                )
                
                if inventory_updates:
                    # Apply updates using deep merge (same pattern as main character updater)
                    from updates.update_character_info import deep_merge_dict
                    corrected_data = deep_merge_dict(character_data, inventory_updates)
                else:
                    # No changes needed
                    corrected_data = character_data

                # Commit the cache only after the complete merge succeeds, and
                # key it to the resulting state rather than the stale input.
                final_inventory_hash = self._compute_inventory_hash(
                    self.extract_inventory_data(corrected_data)
                )
                self._update_inventory_cache(
                    character_name,
                    final_inventory_hash,
                )
                return _validation_result(character_data, corrected_data)
                    
            except Exception as e:
                self.corrections_made = copy.deepcopy(corrections_before)
                self.logger.error(f"AI inventory validation attempt {attempt} failed: {str(e)}")
                attempt += 1
                if attempt > max_attempts:
                    self.logger.error(f"All {max_attempts} inventory validation attempts failed")
                    return _failed_validation_result(character_data, e)
        
        return _failed_validation_result(
            character_data,
            RuntimeError("T052 validation attempts exhausted"),
        )

    def ai_validate_inventory_categories(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Backward-compatible data-only facade for T052."""

        return self.ai_validate_inventory_categories_with_result(character_data).data
    
    def get_validator_system_prompt(self) -> str:
        """
        Comprehensive system prompt for AI character validation
        
        Returns:
            System prompt with 5th edition rules and examples
        """
        # Return cached prompt loaded from file
        if self.ac_prompt:
            return self.ac_prompt
        
        # Fallback to hardcoded prompt if file loading failed
        return """You are an expert character validator for the 5th edition of the world's most popular role playing game. Your job is to validate and correct character data to ensure it follows the rules accurately.

## PRIMARY TASK: ARMOR CLASS VALIDATION

You must validate that the character's Armor Class (AC) is calculated correctly based on their equipped items and apply corrections as needed.

## 5TH EDITION ARMOR CLASS RULES

### Base Armor AC Values:
**Light Armor** (AC = Base + Dex modifier, no limit):
- Padded: 11 AC
- Leather: 11 AC  
- Studded Leather: 12 AC

**Medium Armor** (AC = Base + Dex modifier, max +2):
- Hide: 12 AC
- Chain Shirt: 13 AC
- Scale Mail: 14 AC (stealth disadvantage)
- Breastplate: 14 AC
- Half Plate: 15 AC (stealth disadvantage)

**Heavy Armor** (AC = Base only, no Dex bonus):
- Ring Mail: 14 AC (stealth disadvantage)
- Chain Mail: 16 AC (stealth disadvantage)
- Splint: 17 AC (stealth disadvantage)  
- Plate: 18 AC (stealth disadvantage)

**Shields**: +2 AC when equipped

### AC Calculation Formula:
AC = Base Armor + Dex Modifier (limited by armor type) + Shield Bonus + Fighting Style Bonus + Other Bonuses

### Fighting Style Bonuses:
- **Defense**: +1 AC when wearing any armor
- All other fighting styles: No AC bonus

### Equipment Rules:
- Only ONE base armor piece can be equipped
- Only ONE shield can be equipped
- Multiple armor pieces of same type = conflict (keep highest AC)

## VALIDATION EXAMPLES

### Example 1: Fighter with Chain Mail and Shield
```json
Character Data:
{
  "armorClass": 15,
  "abilities": {"dexterity": 14},
  "classFeatures": [{"name": "Fighting Style: Defense"}],
  "equipment": [
    {"item_name": "Chain Mail", "item_type": "armor", "equipped": true},
    {"item_name": "Shield", "item_type": "armor", "equipped": true}
  ]
}

Calculation:
- Chain Mail: 16 AC (heavy armor, no Dex bonus)
- Shield: +2 AC  
- Defense Fighting Style: +1 AC (wearing armor)
- Correct AC: 16 + 0 + 2 + 1 = 19

Correction Needed: AC should be 19, not 15
```

### Example 2: Rogue with Studded Leather
```json
Character Data:
{
  "armorClass": 14,
  "abilities": {"dexterity": 16},
  "equipment": [
    {"item_name": "Studded Leather", "item_type": "armor", "equipped": true}
  ]
}

Calculation:
- Studded Leather: 12 AC (light armor)
- Dex Modifier: +3 (16 Dex, no limit for light armor)
- Correct AC: 12 + 3 = 15

Correction Needed: AC should be 15, not 14
```

### Example 3: Equipment Conflict Resolution
```json
Character Data:
{
  "equipment": [
    {"item_name": "Chain Mail", "item_type": "armor", "equipped": true},
    {"item_name": "Scale Mail", "item_type": "armor", "equipped": true}
  ]
}

Problem: Two base armor pieces equipped
Solution: Keep Chain Mail (16 AC), unequip Scale Mail (14 AC)
```

## RESPONSE FORMAT

You must respond with a JSON object containing:

```json
{
  "validated_character_data": {
    // Complete corrected character data with proper AC
  },
  "corrections_made": [
    "List of specific corrections made"
  ],
  "ac_calculation_breakdown": {
    "base_armor": "Name and AC value",
    "dex_modifier": "Value applied", 
    "shield_bonus": "Value applied",
    "fighting_style_bonus": "Value applied",
    "total_ac": "Final calculated AC"
  }
}
```

## INSTRUCTIONS

1. **Analyze the character data** to identify all equipped armor and relevant bonuses
2. **Auto-populate missing armor properties** using the reference table above
3. **Resolve equipment conflicts** per 5th edition rules
4. **Calculate correct AC** using the formula and rules
5. **Update character data** with corrections
6. **Provide detailed breakdown** of the calculation

Be thorough but concise. Focus on accuracy and rule compliance."""

    def build_ac_validation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build validation prompt with character data
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Formatted prompt for AI validation
        """
        return f"""Please validate and correct the Armor Class calculation for this character:

```json
{json.dumps(character_data, indent=2)}
```

Analyze their equipment, abilities, and class features to determine the correct AC according to 5th edition rules. 

Pay special attention to:
1. Equipped armor and shields
2. Dexterity modifier and armor type limitations
3. Fighting style bonuses (especially Defense)
4. Equipment conflicts (multiple armor pieces)

Provide the corrected character data with proper AC calculation."""

    def parse_ai_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AI response and extract corrected character data
        
        Args:
            ai_response: AI validation response
            original_data: Original character data
            
        Returns:
            Corrected character data
        """
        parsed_response = _load_response_object(ai_response, "T051")
        expected_root_fields = {
            'validated_character_data',
            'corrections_made',
            'ac_calculation_breakdown',
        }
        if set(parsed_response) != expected_root_fields:
            raise CharacterValidationResponseError(
                "T051: response must contain exactly validated_character_data, "
                "corrections_made, and ac_calculation_breakdown"
            )
        schema_errors = validate_schema(
            parsed_response, CHARACTER_VALIDATOR_SCHEMA, path="response"
        )
        if schema_errors:
            raise CharacterValidationResponseError(
                "T051 schema violation: " + "; ".join(schema_errors)
            )

        response_data = copy.deepcopy(parsed_response['validated_character_data'])
        corrections = _require_string_list(
            parsed_response['corrections_made'],
            "T051: 'corrections_made'",
        )
        if 'armorClass' not in response_data:
            raise CharacterValidationResponseError(
                "T051: validated_character_data requires armorClass"
            )
        corrected_ac = _require_contract_integer(
            response_data['armorClass'],
            "T051: validated_character_data.armorClass",
            minimum=1,
        )
        if corrected_ac > 100:
            raise CharacterValidationResponseError(
                "T051: validated_character_data.armorClass exceeds 100"
            )
        corrected_data = {'armorClass': corrected_ac}

        breakdown = parsed_response['ac_calculation_breakdown']
        breakdown_total = _require_contract_integer(
            breakdown['total_ac'],
            "T051: ac_calculation_breakdown.total_ac",
            minimum=1,
        )
        if breakdown_total != corrected_ac:
            raise CharacterValidationResponseError(
                "T051: breakdown total_ac must match validated armorClass"
            )

        # The model receives an AC-only projection. It may echo that context, but
        # it must not invent top-level character fields or alter non-AC context.
        mutable_fields = {'armorClass', 'equipment'}
        for field, value in response_data.items():
            if field not in original_data:
                raise CharacterValidationResponseError(
                    f"T051: validated_character_data contains unknown field '{field}'"
                )
            if field not in mutable_fields and value != original_data[field]:
                raise CharacterValidationResponseError(
                    f"T051: validated_character_data may not alter context field '{field}'"
                )

        equipment_updates = []
        if 'equipment' in response_data:
            if not isinstance(response_data['equipment'], list):
                raise CharacterValidationResponseError(
                    "T051: validated_character_data.equipment must be an array"
                )
            source_equipment = _source_items_by_name(
                original_data.get('equipment', []),
                "T051: source equipment",
                reject_duplicates=True,
            )
            seen_names = set()
            immutable_equipment_fields = {'item_type', 'description', 'quantity'}
            mutable_equipment_fields = {
                'equipped', 'ac_base', 'ac_bonus', 'dex_limit',
                'armor_category', 'stealth_disadvantage',
            }
            allowed_equipment_fields = {
                'item_name', 'item_type', 'equipped', 'description',
                'ac_base', 'ac_bonus', 'dex_limit', 'armor_category',
                'stealth_disadvantage', 'quantity',
            }
            for index, item in enumerate(response_data['equipment']):
                if not isinstance(item, dict):
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}] must be an object"
                    )
                unknown_fields = set(item).difference(allowed_equipment_fields)
                if unknown_fields:
                    raise CharacterValidationResponseError(
                        "T051: equipment update contains unsupported field(s): "
                        + ", ".join(sorted(unknown_fields))
                    )
                normalized_name = _normalized_name(item.get('item_name'))
                if not normalized_name or normalized_name not in source_equipment:
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}] must reference source equipment"
                    )
                if normalized_name in seen_names:
                    raise CharacterValidationResponseError(
                        f"T051: duplicate equipment update for '{item.get('item_name')}'"
                    )
                seen_names.add(normalized_name)
                source_item = source_equipment[normalized_name]
                for immutable_field in immutable_equipment_fields:
                    if (
                        immutable_field in item
                        and item[immutable_field] != source_item.get(immutable_field)
                    ):
                        raise CharacterValidationResponseError(
                            f"T051: equipment[{index}] may not alter "
                            f"{immutable_field}"
                        )
                if 'equipped' in item and type(item['equipped']) is not bool:
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}].equipped must be a boolean"
                    )
                if 'stealth_disadvantage' in item and type(
                    item['stealth_disadvantage']
                ) is not bool:
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}].stealth_disadvantage must be a boolean"
                    )
                if 'armor_category' in item and not isinstance(
                    item['armor_category'], str
                ):
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}].armor_category must be a string"
                    )
                for numeric_field in ('ac_base', 'ac_bonus', 'dex_limit'):
                    if numeric_field in item and (
                        isinstance(item[numeric_field], bool)
                        or not isinstance(item[numeric_field], (int, float))
                    ):
                        raise CharacterValidationResponseError(
                            f"T051: equipment[{index}].{numeric_field} must be numeric"
                        )

                normalized_update = {'item_name': source_item['item_name']}
                for mutable_field in mutable_equipment_fields:
                    if (
                        mutable_field in item
                        and item[mutable_field] != source_item.get(mutable_field)
                    ):
                        normalized_update[mutable_field] = copy.deepcopy(
                            item[mutable_field]
                        )
                if len(normalized_update) > 1:
                    equipment_updates.append(normalized_update)

        if equipment_updates:
            corrected_data['equipment'] = equipment_updates

        original_ac = original_data.get('armorClass')
        if (corrected_ac != original_ac or equipment_updates) and not corrections:
            raise CharacterValidationResponseError(
                "T051: an AC mutation requires a correction description"
            )

        self.corrections_made = list(corrections)
        for correction in self.corrections_made:
            debug(f"[AC Correction] {correction}", category="character_validation")
            self.logger.info(f"AI Correction: {correction}")

        self.logger.info(f"AC Breakdown: {breakdown}")
        return corrected_data

    def get_inventory_validator_system_prompt(self) -> str:
        """
        System prompt for AI inventory categorization validation

        Returns:
            System prompt with inventory categorization rules
        """
        # Return cached prompt loaded from file
        if self.inventory_prompt:
            return self.inventory_prompt

        # Fallback to hardcoded prompt if file loading failed
        return """You are an expert inventory categorization validator for the 5th edition of the world's most popular role playing game. Your job is to ensure all inventory items are correctly categorized according to standard item types.

## PRIMARY TASK: INVENTORY CATEGORIZATION VALIDATION

You must validate that each item in the character's inventory has the correct item_type based on its name and description.

### VALID ITEM TYPES (use these EXACTLY):
- "weapon" - swords, bows, daggers, melee and ranged weapons
- "armor" - armor pieces, shields, cloaks, boots, gloves, protective wear
- "ammunition" - arrows, bolts, sling bullets, thrown weapon ammo
- "consumable" - potions, scrolls, food, rations, anything consumed when used
- "equipment" - tools, torches, rope, containers, utility items
- "miscellaneous" - rings, amulets, wands, truly miscellaneous items only

### DETAILED CATEGORIZATION RULES:

#### EXCEPTION RULES - DO NOT RE-CATEGORIZE:
- If "Short Sword" is already type "weapon", leave it as is
- If "Shortsword" is already type "weapon", leave it as is  
- If "Longbow" is already type "weapon", leave it as is
- If "Long Bow" is already type "weapon", leave it as is
- If "Crossbow" is already type "weapon", leave it as is
- If "Light Crossbow" is already type "weapon", leave it as is
- If "Studded Leather Armor" is already type "armor", leave it as is
- If "Leather Armor" is already type "armor", leave it as is
- If "Scale Mail" is already type "armor", leave it as is
- If "Shield" is already type "armor", leave it as is
- If "Quiver" is already type "equipment", leave it as is
- If "Pouch" is already type "equipment" or "miscellaneous", leave it as is
- If "Explorer's Pack" is already type "equipment", leave it as is
- If "Torch" is already type "equipment", leave it as is
- If "Rope" is already type "equipment", leave it as is
- If "Waterskin" is already type "equipment", leave it as is
- Items already correctly categorized should not be changed

#### WEAPONS -> "weapon"
- All swords, axes, maces, hammers, daggers
- All bows, crossbows, slings
- Staffs and quarterstaffs used as weapons
- Any item with attack bonus or damage dice

#### ARMOR -> "armor"  
- All armor (leather, chain, plate, etc.)
- Shields of any type
- Helmets, gauntlets, boots IF they provide AC bonus
- Cloaks IF they provide AC or protection
- Robes IF they provide magical protection
- NOTE: Regular gloves are NOT armor unless they're gauntlets with AC bonus

#### AMMUNITION -> "ammunition"
- Arrows, Bolts, Bullets, Darts
- Sling stones, blowgun needles
- Any projectile meant to be fired/thrown multiple times

#### CONSUMABLES -> "consumable"
- ALL potions (healing, magic, alcohol)
- ALL scrolls
- ALL food items (rations, bread, meat, fruit)
- Trail rations, iron rations, dried foods
- Flasks of oil, holy water, acid, alchemist's fire
- Anything that is used up when activated

#### EQUIPMENT -> "equipment"
- Backpacks, sacks, chests, boxes (storage containers)
- Rope, chain, grappling hooks, pitons
- Torches, lanterns, candles (light sources)
- Thieves' tools, healer's kits, tool sets
- Bedrolls, tents, blankets
- Maps, spyglasses, magnifying glasses
- Musical instruments (lute, flute, drums)
- Holy symbols IF actively used for spellcasting
- Component pouches, spell focuses
- Books, tomes, journals (non-magical)
- Climbing gear, explorer's packs
- Regular boots without AC bonus (Sturdy Boots, Leather Boots, Work Boots)
- Regular cloaks without AC bonus (Woolen Cloak, Travel Cloak, Winter Cloak)
- Belts, sashes, bandoliers (weapon belts, tool belts, pouches worn on belt)
- Regular clothing items (tunics, shirts, vests, robes without magical properties)
- Regular hats and hoods (not helmets)

#### MISCELLANEOUS -> "miscellaneous"
- Coin pouches, money bags, pouches of coins (NOT active storage containers)
- Loose coins, gems, pearls, jewelry
- Dice, cards, gaming sets, chess pieces (including "Set of bone dice")
- Lucky charms, tokens, trinkets (non-magical)
- Holy symbols IF kept as keepsakes (not for spellcasting)
- Feathers, twine, small decorative items (including "Crow's Hand Feather")
- Art objects, statuettes, paintings
- Goblets, chalices, ceremonial vessels (unless actively used as tools)
- Letters, notes, deeds, contracts
- Signet rings (non-magical)
- Badges, medals, emblems (including "Insignia of rank")
- Amulets and talismans (non-magical) - ALWAYS miscellaneous unless they provide game mechanics
- Ward charms, protective tokens (non-magical)
- Carved or decorative talismans (keepsakes)
- Military keepsakes, trophies, dog tags (including "Trophy from a fallen enemy", "Dog tag")
- Trade goods, valuable cloth, fabric scraps (including "Torn but valuable cloth")
- Simple pouches and coin containers (including "Pouch")
- Protective gloves without AC bonus (including "Sturdy gloves")

### CRITICAL EDGE CASE RULES:
1. Coin containers (pouches, bags with coins) -> "miscellaneous" NOT "equipment"
2. Gaming items (dice, cards) -> "miscellaneous" NOT "equipment"  
3. Holy symbols -> "equipment" IF used for spellcasting, "miscellaneous" IF keepsake
4. Charms/tokens/wards -> "miscellaneous" for non-magical protective charms (even if they grant resistance)
5. Books -> "equipment" IF spellbooks or reference manuals, "miscellaneous" IF just lore
6. Containers -> "equipment" IF empty/general use, "miscellaneous" IF specifically for coins
7. Jewelry -> "miscellaneous" UNLESS it provides magical effects
8. Tools -> "equipment" IF professional tools, "miscellaneous" IF trinkets
9. Military memorabilia -> "miscellaneous" (insignia, trophies, dog tags are keepsakes)
10. Trade goods -> "miscellaneous" (cloth, fabric, raw materials for trade)
11. SPECIAL CASES THAT ARE ALWAYS MISCELLANEOUS:
    - Yew Ward Charm (protective charm)
    - Insignia of rank (badge/emblem)
    - Trophy from a fallen enemy (keepsake)
    - Set of bone dice (gaming set)
    - Dog tag (keepsake)
    - Pouch (coin container)
    - Crow's Hand Feather (token)
    - Torn but valuable cloth (trade good)
    - Carved bone talisman (charm/talisman)
    - Knight's Heart Amulet (keepsake amulet)
    - Any amulet or talisman (unless it grants mechanical benefits)
    - Enchanted goblet (art object/valuable)
    - Any goblet, chalice, or ceremonial vessel (unless actively used as equipment)
12. SPECIAL CASES FOR GLOVES:
    - Sturdy gloves -> "miscellaneous" (protective but no AC bonus)
    - Work gloves -> "equipment" (utility gloves for tasks)
    - Gauntlets -> "armor" (combat protection with AC bonus)
13. SPECIAL CASES FOR BOOTS AND CLOAKS:
    - Regular boots (Sturdy Boots, Leather Boots, etc.) -> "equipment" (worn but no AC bonus)
    - Regular cloaks (Woolen Cloak, Travel Cloak, etc.) -> "equipment" (worn but no AC bonus)
    - Armored boots or magical boots with AC -> "armor"
    - Cloaks of protection or with AC bonus -> "armor"
14. SPECIAL CASES FOR OTHER WEARABLES:
    - Regular belts, sashes -> "equipment" (utility items)
    - Regular clothing (tunics, shirts, vests) -> "equipment" (worn but no AC)
    - Regular hats, hoods -> "equipment" (worn but no AC)
    - Helmets or hats with AC bonus -> "armor"
    - Magical robes with protection -> "armor"
    - Bracers without AC bonus -> "equipment"
    - Bracers of defense or with AC bonus -> "armor"

### OUTPUT FORMAT:
Return a JSON object with ONLY the changes needed:
{
  "corrections_made": ["list of corrections"],
  "equipment": [
    {
      "item_name": "exact item name",
      "item_type": "corrected_type"
    }
  ]
}

CRITICAL: Only return items that need their item_type corrected. Do NOT return items that are already correctly categorized. Do NOT return the complete character data - only the equipment items that need item_type fixes.
"""
    
    def build_inventory_validation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build validation prompt for inventory categorization
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Formatted prompt for AI validation
        """
        equipment = character_data.get('equipment', [])
        
        prompt = f"""Please validate the inventory categorization for this character:

CHARACTER NAME: {character_data.get('name', 'Unknown')}

CURRENT INVENTORY:
"""
        
        for i, item in enumerate(equipment):
            item_name = item.get('item_name', 'Unknown Item')
            item_type = item.get('item_type', 'Unknown')
            description = item.get('description', 'No description')
            quantity = item.get('quantity', 1)
            
            prompt += f"""
Item #{i+1}:
- Name: {item_name}
- Current Type: {item_type}
- Description: {description}
- Quantity: {quantity}
"""
        
        prompt += """

Validate each item's categorization and correct any that are wrong. Focus especially on:
- Items currently marked as "miscellaneous" that should be other types
- Arrows/ammunition items
- Food/rations that should be "consumable"  
- Tools/torches that should be "equipment"

IMPORTANT: Return ONLY the items that need their item_type corrected. Do not include items that are already correctly categorized."""
        
        return prompt
    
    def parse_inventory_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AI inventory validation response - returns only the updates/changes
        
        Args:
            ai_response: AI response string
            original_data: Original character data
            
        Returns:
            Dictionary with only the changes to apply (or empty dict if no changes)
        """
        parsed_response = _load_response_object(ai_response, "T052")
        if set(parsed_response) != {'corrections_made', 'equipment'}:
            raise CharacterValidationResponseError(
                "T052: response must contain exactly corrections_made and equipment"
            )
        equipment = parsed_response.get('equipment')
        corrections = parsed_response.get('corrections_made', [])
        if not isinstance(equipment, list):
            raise CharacterValidationResponseError(
                "T052: 'equipment' must be an array"
            )
        _require_string_list(corrections, "T052: 'corrections_made'")
        source_equipment = _source_items_by_name(
            original_data.get('equipment', []),
            "T052: source equipment",
            reject_duplicates=True,
        )
        normalized_equipment = []
        seen_names = set()
        for index, item in enumerate(equipment):
            if not isinstance(item, dict):
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] must be an object"
                )
            unknown_fields = set(item).difference({'item_name', 'item_type'})
            if unknown_fields:
                raise CharacterValidationResponseError(
                    "T052: equipment update contains unsupported field(s): "
                    + ", ".join(sorted(unknown_fields))
                )
            if not isinstance(item.get('item_name'), str) or not isinstance(
                item.get('item_type'), str
            ):
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] requires string item_name/item_type"
                )
            normalized_name = _normalized_name(item['item_name'])
            if normalized_name not in source_equipment:
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] must reference a source candidate"
                )
            if normalized_name in seen_names:
                raise CharacterValidationResponseError(
                    f"T052: duplicate correction for '{item['item_name']}'"
                )
            seen_names.add(normalized_name)

            normalized_type = item['item_type'].strip().lower()
            if normalized_type not in VALID_INVENTORY_ITEM_TYPES:
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}].item_type is not allowed"
                )
            source_item = source_equipment[normalized_name]
            source_type = str(source_item.get('item_type', '')).strip().lower()
            if normalized_type == source_type:
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] does not change item_type"
                )
            normalized_equipment.append({
                'item_name': source_item['item_name'],
                'item_type': normalized_type,
            })

        for correction in corrections:
            debug(f"[Inventory Correction] {correction}", category="character_validation")
            self.logger.info(f"AI Inventory Correction: {correction}")
            self.corrections_made.append(f"Inventory: {correction}")

        if normalized_equipment:
            return {"equipment": normalized_equipment}
        self.logger.debug("No inventory corrections needed")
        return {}
    
    def validate_character_file_safe(self, file_path: str) -> tuple[Dict[str, Any], bool]:
        """
        Validate character file using atomic file operations
        
        Args:
            file_path: Path to character JSON file
            
        Returns:
            Tuple of (character_data, success_flag)
        """
        # A false legacy flag is reserved for storage failure. Provider and
        # response-contract failures are deliberately fail-open.
        try:
            source_data = safe_read_json(file_path)
        except Exception as e:
            self.logger.error(f"Could not read character file {file_path}: {e}")
            return {}, False
        if source_data is None:
            self.logger.error(f"Could not read character file {file_path}")
            return {}, False

        character_data = source_data
        repair_changes = []
        validation_success = False
        validation_error = None
        try:
            if isinstance(source_data, dict):
                character_data, repair_changes = repair_required_ammunition_field(
                    source_data
                )

            # AI validation and correction.  The explicit result distinguishes
            # provider/contract exhaustion from an authoritative no-op.
            validation_result = self.validate_and_correct_character_with_result(
                character_data
            )
            validation_success = validation_result.success
            validation_error = validation_result.error
            corrected_data = validation_result.data
        except Exception as e:
            # Preserve any deterministic pre-provider repair that completed.
            corrected_data = character_data
            validation_error = str(e)

        if not validation_success:
            self.logger.warning(
                f"Character provider validation failed open for {file_path}: "
                f"{validation_error or 'validation unavailable'}. "
                "Deterministic repairs are retained."
            )

        # Persist any actual state change, including pre-provider contract
        # repair and deterministic repairs carried by a FAILED result.
        if corrected_data != source_data or repair_changes:
            # DEBUG: Check XP before saving corrections
            if (
                isinstance(character_data, dict)
                and isinstance(corrected_data, dict)
                and 'experience_points' in character_data
                and 'experience_points' in corrected_data
            ):
                original_xp = character_data.get('experience_points', 0)
                corrected_xp = corrected_data.get('experience_points', 0)
                if original_xp != corrected_xp:
                    print(f"[DEBUG VALIDATOR XP] WARNING: Validator changing XP from {original_xp} to {corrected_xp}")
                else:
                    print(f"[DEBUG VALIDATOR XP] Validator preserving XP: {corrected_xp}")

            try:
                success = safe_write_json(file_path, corrected_data)
            except Exception as e:
                self.logger.error(
                    f"Failed to save corrected character data to {file_path}: {e}"
                )
                return character_data, False
            if success:
                self.logger.info(f"Character file validated and corrected: {file_path}")
                return corrected_data, True
            else:
                self.logger.error(f"Failed to save corrected character data to {file_path}")
                return character_data, False

        if validation_success:
            self.logger.debug(f"Character file validated - no corrections needed: {file_path}")
        else:
            self.logger.debug(
                f"Character provider validation failed open without state changes: {file_path}"
            )
        return corrected_data, True
    
    def ai_validate_all_batched_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        OPTIMIZED: Batch all AI validations into a single request
        Combines AC validation, inventory categorization, currency consolidation, and class feature validation
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with all AI corrections applied
        """
        character_name = character_data.get('name', 'Unknown')
        
        # Build combined validation prompt
        validation_prompt = self.build_combined_validation_prompt(character_data)

        # Select model config per provider
        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            batch_config = config.CHAR_VALIDATOR_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            batch_config = config.CHAR_VALIDATOR_T053_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            batch_config = config.CHAR_VALIDATOR_LMSTUDIO
        else:  # legacy
            batch_config = config.CHAR_VALIDATOR_LEGACY

        # HIGH-2: retry transient failures up to 3x, matching siblings T052
        # (line ~1119) and T054 (line ~2123). Previously a single try/except
        # skipped ALL four validations (AC + inventory + currency + class
        # feature) on any blip with no retry. The final fail-open
        # `return character_data` is preserved as the safety net: on exhausted
        # retries the character is returned unchanged (a skipped correction,
        # never corruption). The retry only re-attempts to obtain a good
        # response; parse_combined_validation_response is unchanged, so no
        # section applies corrections more aggressively.
        max_attempts = 3
        attempt = 1
        corrections_before = copy.deepcopy(self.corrections_made)
        last_error: BaseException = RuntimeError("T053 validation attempts exhausted")
        while attempt <= max_attempts:
            try:
                response = capture_and_fanout("T053", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": self.get_combined_validator_system_prompt()},
                        {"role": "user", "content": validation_prompt}
                    ],
                    model=batch_config["model"],
                    temperature=0.1,
                    **{k: v for k, v in batch_config.items() if k != "model"})

                # Track usage if available
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_data'})
                    except:
                        pass

                ai_response = response.choices[0].message.content.strip()

                # Parse AI response to get all corrections
                corrected_data = self.parse_combined_validation_response(ai_response, character_data)

                return _validation_result(character_data, corrected_data)

            except Exception as e:
                last_error = e
                self.corrections_made = copy.deepcopy(corrections_before)
                self.logger.error(f"Batched AI validation failed (attempt {attempt}/{max_attempts}): {str(e)}")
                attempt += 1

        # All attempts exhausted: fail open -- return the character unchanged.
        return _failed_validation_result(character_data, last_error)

    def ai_validate_all_batched(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Backward-compatible data-only facade for T053."""

        return self.ai_validate_all_batched_with_result(character_data).data
    
    def get_combined_validator_system_prompt(self) -> str:
        """
        System prompt for combined validation tasks
        """
        return """You are an expert character validator for the 5th edition of the world's most popular role playing game. 
You must perform FOUR validation tasks in a single response:

1. ARMOR CLASS VALIDATION
2. INVENTORY CATEGORIZATION
3. CURRENCY CONSOLIDATION
4. CLASS FEATURE VALIDATION

## TASK 1: ARMOR CLASS VALIDATION

Validate the Armor Class calculation based on equipped armor, shields, and abilities.

AC Calculation Rules:
- Base AC = 10 + Dexterity modifier (if no armor)
- With armor: Use armor's base AC + allowed Dexterity modifier
- Shield: +2 AC (if equipped)
- Special abilities may add bonuses

Common armor types:
- Leather Armor: 11 + Dex modifier
- Studded Leather: 12 + Dex modifier  
- Chain Shirt: 13 + Dex modifier (max 2)
- Scale Mail: 14 + Dex modifier (max 2)
- Chain Mail: 16 (no Dex)
- Plate: 18 (no Dex)

## TASK 2: INVENTORY CATEGORIZATION

""" + self.get_inventory_validator_system_prompt() + """

## TASK 3: CURRENCY CONSOLIDATION

""" + self.get_inventory_consolidation_system_prompt() + """

## TASK 4: CLASS FEATURE VALIDATION

Check for duplicate or outdated class features that should have been replaced during level up.

Common issues to check:
1. Multiple versions of the same feature (e.g., "Channel Divinity (1/rest)" and "Channel Divinity (2/rest)")
2. Features with usage counts in the name that should be consolidated
3. Outdated feature descriptions that don't match current level

Rules:
- When a feature upgrades (like Channel Divinity uses increasing), the old version should be removed
- Features like "Sneak Attack (1d6)" should be replaced by "Sneak Attack (2d6)", not kept as duplicates
- Look for features with parenthetical usage counts or dice values that indicate versions
- Only request removal when the source contains an exact duplicate or a clearly newer numeric version with the same base name/format
- For exact duplicates, remove duplicate copies while retaining one copy
- Never remove a unique feature based only on general game knowledge

## COMBINED OUTPUT FORMAT:

Return a single JSON response with all corrections:
{
  "ac_validation": {
    "current_ac": 17,
    "calculated_ac": 16,
    "correction_needed": true,
    "breakdown": "Scale Mail (14) + Dex mod (+1) + Shield (+2) = 17",
    "corrections": ["AC should be 17, not 16"]
  },
  "inventory_corrections": {
    "corrections_made": ["List of inventory corrections"],
    "equipment": [
      {
        "item_name": "exact item name",
        "item_type": "corrected_type"
      }
    ]
  },
  "currency_consolidation": {
    "corrections_made": ["List of consolidation actions"],
    "currency": {
      "gold": 125,
      "silver": 50,
      "copper": 200
    },
    "items_to_remove": ["5 gold pieces", "bag of 50 gold"],
    "ammunition": [
      {"name": "Arrow", "quantity": 30}
    ],
    "ammo_items_to_remove": ["Arrows x 20"]
  },
  "class_feature_validation": {
    "duplicates_found": ["List of duplicate features to remove"],
    "corrections_made": ["Channel Divinity (1/rest) should be removed - superseded by Channel Divinity (2/rest)"],
    "features_to_remove": ["Channel Divinity (1/rest)"]
  }
}

IMPORTANT: Perform ALL FOUR validations and return results for each in the combined JSON response.
"""
    
    def build_combined_validation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build a combined prompt for all validations
        """
        character_name = character_data.get('name', 'Unknown')
        
        # Get individual prompts
        ac_prompt = self.build_ac_validation_prompt(character_data)
        inventory_prompt = self.build_inventory_validation_prompt(character_data)
        consolidation_prompt = self.build_inventory_consolidation_prompt(character_data)
        
        combined_prompt = f"""Please validate ALL aspects of this character in a single response:

CHARACTER NAME: {character_name}

=== TASK 1: ARMOR CLASS VALIDATION ===
{ac_prompt}

=== TASK 2: INVENTORY CATEGORIZATION ===
{inventory_prompt}

=== TASK 3: CURRENCY CONSOLIDATION ===
{consolidation_prompt}

=== TASK 4: CLASS FEATURE VALIDATION ===
Class Features:
{json.dumps(character_data.get('classFeatures', []), indent=2)}

Check for duplicate features that should have been replaced during level up (e.g., "Channel Divinity (1/rest)" vs "Channel Divinity (2/rest)").

Remember to return a single JSON response with all four validation results."""
        
        return combined_prompt
    
    def parse_combined_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the combined AI validation response
        """
        parsed_response = _load_response_object(ai_response, "T053")
        required_sections = {
            'ac_validation',
            'inventory_corrections',
            'currency_consolidation',
            'class_feature_validation',
        }
        missing_sections = required_sections.difference(parsed_response)
        if missing_sections:
            raise CharacterValidationResponseError(
                "T053: missing section(s): " + ", ".join(sorted(missing_sections))
            )
        for section in required_sections:
            if not isinstance(parsed_response[section], dict):
                raise CharacterValidationResponseError(
                    f"T053: '{section}' must be an object"
                )
        extra_sections = set(parsed_response).difference(required_sections)
        if extra_sections:
            raise CharacterValidationResponseError(
                "T053: unsupported top-level section(s): "
                + ", ".join(sorted(extra_sections))
            )

        result_data = copy.deepcopy(original_data)
        correction_messages = []
        source_equipment = _source_items_by_name(
            original_data.get('equipment', []),
            "T053: source equipment",
            reject_duplicates=True,
        )

        # Process AC validation
        ac_result = parsed_response['ac_validation']
        allowed_ac_fields = {
            'current_ac', 'calculated_ac', 'correction_needed', 'breakdown',
            'corrections',
        }
        if set(ac_result).difference(allowed_ac_fields):
            raise CharacterValidationResponseError(
                "T053: ac_validation contains unsupported fields"
            )
        if type(ac_result.get('correction_needed')) is not bool:
            raise CharacterValidationResponseError(
                "T053: ac_validation.correction_needed must be a boolean"
            )
        source_ac = _require_contract_integer(
            original_data.get('armorClass', 10),
            "T053: source armorClass",
            minimum=1,
        )
        if 'current_ac' in ac_result:
            reported_current_ac = _require_contract_integer(
                ac_result['current_ac'],
                "T053: ac_validation.current_ac",
                minimum=1,
            )
            if reported_current_ac != source_ac:
                raise CharacterValidationResponseError(
                    "T053: ac_validation.current_ac must match source armorClass"
                )
        ac_corrections = _require_string_list(
            ac_result.get('corrections', []),
            "T053: ac_validation.corrections",
        )
        if ac_result['correction_needed']:
            if 'calculated_ac' not in ac_result:
                raise CharacterValidationResponseError(
                    "T053: calculated_ac is required when correction_needed is true"
                )
            calculated_ac = _require_contract_integer(
                ac_result['calculated_ac'],
                "T053: ac_validation.calculated_ac",
                minimum=1,
            )
            if calculated_ac > 100:
                raise CharacterValidationResponseError(
                    "T053: ac_validation.calculated_ac exceeds 100"
                )
            if not ac_corrections:
                raise CharacterValidationResponseError(
                    "T053: an AC change requires a correction description"
                )
            result_data['armorClass'] = calculated_ac
        elif 'calculated_ac' in ac_result:
            calculated_ac = _require_contract_integer(
                ac_result['calculated_ac'],
                "T053: ac_validation.calculated_ac",
                minimum=1,
            )
            if calculated_ac != source_ac:
                raise CharacterValidationResponseError(
                    "T053: calculated_ac conflicts with correction_needed=false"
                )
        if 'breakdown' in ac_result and not isinstance(ac_result['breakdown'], str):
            raise CharacterValidationResponseError(
                "T053: ac_validation.breakdown must be a string"
            )
        correction_messages.extend(ac_corrections)

        # Process inventory corrections
        inv_result = parsed_response['inventory_corrections']
        if set(inv_result).difference({'corrections_made', 'equipment'}):
            raise CharacterValidationResponseError(
                "T053: inventory_corrections contains unsupported fields"
            )
        correction_messages.extend(_require_string_list(
            inv_result.get('corrections_made', []),
            "T053: inventory_corrections.corrections_made",
        ))
        inventory_equipment = inv_result.get('equipment', [])
        if not isinstance(inventory_equipment, list):
            raise CharacterValidationResponseError(
                "T053: inventory_corrections.equipment must be an array"
            )
        normalized_inventory_updates = []
        seen_inventory_names = set()
        for index, item in enumerate(inventory_equipment):
            if not isinstance(item, dict) or set(item) != {'item_name', 'item_type'}:
                raise CharacterValidationResponseError(
                    f"T053: inventory_corrections.equipment[{index}] requires only item_name/item_type"
                )
            item_name = _normalized_name(item.get('item_name'))
            if item_name not in source_equipment:
                raise CharacterValidationResponseError(
                    f"T053: inventory correction {index} must reference source equipment"
                )
            if item_name in seen_inventory_names:
                raise CharacterValidationResponseError(
                    f"T053: duplicate inventory correction for '{item.get('item_name')}'"
                )
            seen_inventory_names.add(item_name)
            item_type = item.get('item_type')
            if not isinstance(item_type, str) or item_type.strip().lower() not in VALID_INVENTORY_ITEM_TYPES:
                raise CharacterValidationResponseError(
                    f"T053: inventory correction {index} has invalid item_type"
                )
            source_item = source_equipment[item_name]
            normalized_type = item_type.strip().lower()
            if normalized_type == str(source_item.get('item_type', '')).strip().lower():
                raise CharacterValidationResponseError(
                    f"T053: inventory correction {index} does not change item_type"
                )
            normalized_inventory_updates.append({
                'item_name': source_item['item_name'],
                'item_type': normalized_type,
            })
        if normalized_inventory_updates:
            from updates.update_character_info import deep_merge_dict
            inventory_updates = {'equipment': normalized_inventory_updates}
            result_data = deep_merge_dict(result_data, inventory_updates)

        # Process currency consolidation
        curr_result = parsed_response['currency_consolidation']
        allowed_currency_fields = {
            'corrections_made', 'currency', 'items_to_remove', 'ammunition',
            'ammo_items_to_remove',
        }
        if set(curr_result).difference(allowed_currency_fields):
            raise CharacterValidationResponseError(
                "T053: currency_consolidation contains unsupported fields"
            )
        correction_messages.extend(_require_string_list(
            curr_result.get('corrections_made', []),
            "T053: currency_consolidation.corrections_made",
        ))
        current_currency = original_data.get('currency', {})
        if not isinstance(current_currency, dict):
            raise CharacterValidationResponseError(
                "T053: source currency must be an object"
            )
        currency_updates = curr_result.get('currency', {})
        if not isinstance(currency_updates, dict):
            raise CharacterValidationResponseError(
                "T053: currency_consolidation.currency must be an object"
            )
        unsupported_denominations = set(currency_updates).difference(
            VALID_CURRENCY_FIELDS
        )
        if unsupported_denominations:
            raise CharacterValidationResponseError(
                "T053: currency_consolidation has unsupported denominations"
            )
        normalized_currency_updates = {}
        currency_deltas = {}
        for denomination, value in currency_updates.items():
            new_total = _require_contract_integer(
                value,
                f"T053: currency_consolidation.currency.{denomination}",
                minimum=0,
            )
            old_total = _require_contract_integer(
                current_currency.get(denomination, 0),
                f"T053: source currency.{denomination}",
                minimum=0,
            )
            if new_total < old_total:
                raise CharacterValidationResponseError(
                    f"T053: currency.{denomination} may not decrease"
                )
            if new_total != old_total:
                normalized_currency_updates[denomination] = new_total
                currency_deltas[denomination] = new_total - old_total

        items_to_remove = _require_string_list(
            curr_result.get('items_to_remove', []),
            "T053: currency_consolidation.items_to_remove",
        )
        ammo_items_to_remove = _require_string_list(
            curr_result.get('ammo_items_to_remove', []),
            "T053: currency_consolidation.ammo_items_to_remove",
        )
        normalized_currency_removals = {
            _normalized_name(item_name) for item_name in items_to_remove
        }
        normalized_ammo_removals = {
            _normalized_name(item_name) for item_name in ammo_items_to_remove
        }
        if len(normalized_currency_removals) != len(items_to_remove):
            raise CharacterValidationResponseError(
                "T053: items_to_remove contains an empty or duplicate name"
            )
        if len(normalized_ammo_removals) != len(ammo_items_to_remove):
            raise CharacterValidationResponseError(
                "T053: ammo_items_to_remove contains an empty or duplicate name"
            )
        if normalized_currency_removals.intersection(normalized_ammo_removals):
            raise CharacterValidationResponseError(
                "T053: an equipment item may not fund both currency and ammunition"
            )
        for field_name, removal_names in (
            ('items_to_remove', normalized_currency_removals),
            ('ammo_items_to_remove', normalized_ammo_removals),
        ):
            unknown_names = removal_names.difference(source_equipment)
            if unknown_names:
                raise CharacterValidationResponseError(
                    f"T053: {field_name} references unknown equipment "
                    + ", ".join(sorted(unknown_names))
                )

        currency_source_items = [
            source_equipment[name] for name in sorted(normalized_currency_removals)
        ]
        ammo_source_items = [
            source_equipment[name] for name in sorted(normalized_ammo_removals)
        ]
        for index, item in enumerate(currency_source_items):
            item_path = f"T053: items_to_remove[{index}]"
            _require_destructively_safe_source_item(item, item_path)
            if not _currency_evidence_from_item(item, item_path):
                raise CharacterValidationResponseError(
                    "T053 currency conservation requires an unambiguous numeric "
                    "currency source for every removed item"
                )
            if _ammunition_evidence_from_item(item, item_path):
                raise CharacterValidationResponseError(
                    "T053 currency source ambiguously contains ammunition"
                )
        for index, item in enumerate(ammo_source_items):
            item_path = f"T053: ammo_items_to_remove[{index}]"
            _require_destructively_safe_source_item(item, item_path)
            if _supported_container_rename(item) is not None:
                raise CharacterValidationResponseError(
                    "T053 may not delete an ammunition container; use the "
                    "dedicated consolidation path to standardize it"
                )
            if not _ammunition_evidence_from_item(
                item,
                item_path,
            ):
                raise CharacterValidationResponseError(
                    "T053 ammunition conservation requires an unambiguous numeric "
                    "standard-ammunition source for every removed item"
                )
            if _currency_evidence_from_item(item, item_path):
                raise CharacterValidationResponseError(
                    "T053 ammunition source ambiguously contains currency"
                )

        currency_evidence = _aggregate_evidence(
            currency_source_items,
            _currency_evidence_from_item,
            "T053: items_to_remove",
        )
        _require_exact_conservation(
            "T053 currency",
            currency_deltas,
            currency_evidence,
        )
        if normalized_currency_updates:
            result_data.setdefault('currency', {}).update(normalized_currency_updates)

        normalized_removals = normalized_currency_removals.union(
            normalized_ammo_removals
        )
        if normalized_removals and 'equipment' in result_data:
            result_data['equipment'] = [
                item for item in result_data['equipment']
                if _normalized_name(item.get('item_name')) not in normalized_removals
            ]

        ammunition = curr_result.get('ammunition', [])
        if not isinstance(ammunition, list):
            raise CharacterValidationResponseError(
                "T053: currency_consolidation.ammunition must be an array"
            )
        source_ammunition = {}
        source_ammunition_rows = original_data.get('ammunition', [])
        _require_unique_source_ammunition(
            source_ammunition_rows,
            "T053: source ammunition",
        )
        for source_index, source_ammo in enumerate(source_ammunition_rows):
            if not isinstance(source_ammo, dict):
                raise CharacterValidationResponseError(
                    f"T053: source ammunition[{source_index}] must be an object"
                )
            canonical_name = _canonical_ammunition_name(source_ammo.get('name'))
            if canonical_name is None:
                continue
            source_total = _require_contract_integer(
                source_ammo.get('quantity', 0),
                f"T053: source ammunition[{source_index}].quantity",
                minimum=0,
            )
            entry = source_ammunition.setdefault(
                canonical_name,
                {'name': source_ammo.get('name'), 'quantity': 0},
            )
            entry['quantity'] += source_total
        ammunition_deltas = []
        ammunition_delta_totals = {}
        seen_ammunition = set()
        for index, ammo in enumerate(ammunition):
            if not isinstance(ammo, dict) or set(ammo).difference(
                {'name', 'quantity', 'description'}
            ):
                raise CharacterValidationResponseError(
                    f"T053: currency_consolidation.ammunition[{index}] is invalid"
                )
            ammo_name = _canonical_ammunition_name(ammo.get('name'))
            if ammo_name is None or ammo_name in seen_ammunition:
                raise CharacterValidationResponseError(
                    f"T053: ammunition[{index}] requires a unique standard name"
                )
            seen_ammunition.add(ammo_name)
            source_entry = source_ammunition.get(ammo_name, {})
            old_total = _require_contract_integer(
                source_entry.get('quantity', 0),
                f"T053: source ammunition[{ammo_name}].quantity",
                minimum=0,
            )
            new_total = _require_contract_integer(
                ammo.get('quantity'),
                f"T053: ammunition[{index}].quantity",
                minimum=0,
            )
            if new_total < old_total:
                raise CharacterValidationResponseError(
                    f"T053: ammunition total for '{ammo.get('name')}' may not decrease"
                )
            if new_total != old_total:
                delta = copy.deepcopy(ammo)
                delta['name'] = source_entry.get('name', ammo['name'].strip())
                delta['quantity'] = new_total - old_total
                # Quantity consolidation must not let a provider author new
                # item prose. Existing descriptions survive the merge; new
                # standard ammunition receives the deterministic merge default.
                delta.pop('description', None)
                ammunition_deltas.append(delta)
                ammunition_delta_totals[ammo_name] = new_total - old_total

        ammunition_evidence = _aggregate_evidence(
            ammo_source_items,
            _ammunition_evidence_from_item,
            "T053: ammo_items_to_remove",
        )
        _require_exact_conservation(
            "T053 ammunition",
            ammunition_delta_totals,
            ammunition_evidence,
        )
        if ammunition_deltas:
            from updates.update_character_info import deep_merge_dict
            result_data = deep_merge_dict(
                result_data,
                {'ammunition': ammunition_deltas},
            )

        # Process class feature validation
        feat_result = parsed_response['class_feature_validation']
        allowed_feature_fields = {
            'duplicates_found', 'corrections_made', 'features_to_remove',
        }
        if set(feat_result).difference(allowed_feature_fields):
            raise CharacterValidationResponseError(
                "T053: class_feature_validation contains unsupported fields"
            )
        correction_messages.extend(_require_string_list(
            feat_result.get('corrections_made', []),
            "T053: class_feature_validation.corrections_made",
        ))
        _require_string_list(
            feat_result.get('duplicates_found', []),
            "T053: class_feature_validation.duplicates_found",
        )
        features_to_remove = _require_string_list(
            feat_result.get('features_to_remove', []),
            "T053: class_feature_validation.features_to_remove",
        )
        source_feature_list = original_data.get('classFeatures', [])
        if not isinstance(source_feature_list, list):
            raise CharacterValidationResponseError(
                "T053: source classFeatures must be an array"
            )
        normalized_requests = [_normalized_name(name) for name in features_to_remove]
        if (
            any(not name for name in normalized_requests)
            or len(set(normalized_requests)) != len(normalized_requests)
        ):
            raise CharacterValidationResponseError(
                "T053: features_to_remove contains an empty or duplicate name"
            )

        feature_indices_to_remove = set()
        source_feature_names = [
            feature.get('name') if isinstance(feature, dict) else None
            for feature in source_feature_list
        ]
        for feature_name in features_to_remove:
            normalized_name = _normalized_name(feature_name)
            matching_indices = [
                index
                for index, feature in enumerate(source_feature_list)
                if isinstance(feature, dict)
                and _normalized_name(feature.get('name')) == normalized_name
            ]
            if not matching_indices:
                raise CharacterValidationResponseError(
                    f"T053: features_to_remove references unknown feature '{feature_name}'"
                )

            matching_features = [source_feature_list[index] for index in matching_indices]
            if (
                len(matching_features) > 1
                and all(feature == matching_features[0] for feature in matching_features[1:])
            ):
                # Retain one exact source duplicate and remove only the extras.
                feature_indices_to_remove.update(matching_indices[1:])
                continue

            if len(matching_indices) != 1 or not _strictly_newer_feature(
                source_feature_list[matching_indices[0]].get('name'),
                [
                    name
                    for index, name in enumerate(source_feature_names)
                    if index != matching_indices[0]
                ],
            ):
                raise CharacterValidationResponseError(
                    f"T053: feature '{feature_name}' has no exact duplicate or "
                    "demonstrably newer source version"
                )
            feature_indices_to_remove.add(matching_indices[0])

        if feature_indices_to_remove and isinstance(
            result_data.get('classFeatures'), list
        ):
            result_data['classFeatures'] = [
                feature
                for index, feature in enumerate(result_data['classFeatures'])
                if index not in feature_indices_to_remove
            ]

        # Only publish correction messages after every section validates and all
        # in-memory merges have completed. A late-section failure is all-or-none.
        self.corrections_made.extend(correction_messages)

        return result_data
    
    def validate_status_condition_consistency(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and correct status-condition consistency
        
        Ensures that status, condition, and hitPoints fields are logically consistent:
        - If status is "alive" and hitPoints > 0, condition cannot be "unconscious"
        - If healing an unconscious character, clear unconscious conditions
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with corrected status-condition consistency
        """
        
        status = character_data.get("status", "alive")
        condition = character_data.get("condition", "none")
        condition_affected = character_data.get("condition_affected", [])
        hit_points = character_data.get("hitPoints", 0)
        
        # Check for inconsistent state: alive with HP > 0 but unconscious condition
        if (status == "alive" and 
            hit_points > 0 and 
            (condition == "unconscious" or "unconscious" in condition_affected)):
            
            # Create a copy of character data to modify
            corrected_data = character_data.copy()
            
            # Clear unconscious conditions
            corrected_data["condition"] = "none"
            corrected_data["condition_affected"] = [c for c in condition_affected if c != "unconscious"]
            
            # Log the correction
            self.corrections_made.append({
                "type": "status_condition_consistency",
                "issue": f"Character had status='alive' with hitPoints={hit_points} but condition was unconscious",
                "correction": "Cleared unconscious condition and condition_affected"
            })
            
            self.logger.info(f"Corrected status-condition inconsistency: status={status}, HP={hit_points}, cleared unconscious condition")
            
            return corrected_data
        
        # Check for opposite case: unconscious status but no unconscious condition
        elif status == "unconscious" and condition != "unconscious":
            # Create a copy of character data to modify
            corrected_data = character_data.copy()
            
            # Set unconscious conditions
            corrected_data["condition"] = "unconscious"
            if "unconscious" not in corrected_data.get("condition_affected", []):
                corrected_data["condition_affected"] = corrected_data.get("condition_affected", []) + ["unconscious"]
            
            # Log the correction
            self.corrections_made.append({
                "type": "status_condition_consistency", 
                "issue": f"Character had status='unconscious' but condition was not unconscious",
                "correction": "Set condition to unconscious and added to condition_affected"
            })
            
            self.logger.info(f"Corrected status-condition inconsistency: status={status}, set unconscious condition")
            
            return corrected_data
        
        # No corrections needed
        return character_data
    
    def ai_consolidate_inventory_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        Use AI to consolidate loose currency and ammunition into their proper sections with caching
        Following the main character updater pattern: return only changes, use deep merge
        
        Consolidates:
        - Loose coins (e.g., "5 gold pieces") into currency
        - Emptied coin bags (e.g., "bag of 50 gold") into currency
        - Ammunition items (e.g., "Crossbow bolts x 10") into ammunition section
        
        Preserves:
        - Gems and valuables (e.g., "ruby worth 150 gold")
        - Containers with contents (e.g., "chest containing 1000 gold")
        - Art objects and trade goods
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with consolidated currency and ammunition (from cache if unchanged)
        """
        
        # Extract only currency/ammo relevant data
        consolidation_data = self.extract_currency_consolidation_data(character_data)
        
        # Compute hash of consolidation data
        character_name = character_data.get('name', 'Unknown')
        currency_hash = self._compute_currency_hash(consolidation_data)
        
        # Check if validation is cached and unchanged
        if self._is_currency_validation_cached(character_name, currency_hash):
            # Return original data - no changes needed since cached validation passed
            print(f"DEBUG: [Validation Cache] Skipping currency consolidation for {character_name} - data unchanged")
            info(f"[Validation Cache] Skipping currency consolidation for {character_name} - data unchanged", category="character_validation")
            
            # Log cache hit statistics
            if character_name in self.validation_cache:
                cache_entry = self.validation_cache[character_name]
                debug(f"[Validation Cache] Last validated: {cache_entry.get('last_currency_validation')}", category="character_validation")
            
            return CharacterValidationResult(
                character_data,
                CharacterValidationStatus.NO_CHANGE,
            )
        
        # If no items need consolidation, skip API call
        if len(consolidation_data['equipment']) == 0:
            print(f"DEBUG: [Currency Consolidation] No currency/ammo items found for {character_name} - skipping consolidation")
            info(f"[Currency Consolidation] No currency/ammo items found for {character_name} - skipping consolidation", category="character_validation")
            # Update cache to avoid checking again
            self._update_currency_cache(character_name, currency_hash)
            return CharacterValidationResult(
                character_data,
                CharacterValidationStatus.NO_CHANGE,
            )
        
        # Data has changed or not cached - perform consolidation
        print(f"DEBUG: [AI Validator] Checking {character_name}'s inventory for consolidation opportunities...")
        info(f"[Validation Cache] Running currency consolidation for {character_name} - {len(consolidation_data['equipment'])} items to check", category="character_validation")
        
        max_attempts = 3
        attempt = 1
        corrections_before = copy.deepcopy(self.corrections_made)
        
        while attempt <= max_attempts:
            try:
                # Build prompt with filtered data
                consolidation_prompt = self.build_inventory_consolidation_prompt(consolidation_data)

                # Select model config per provider
                from model_config import MODEL_PROVIDER
                if MODEL_PROVIDER == "openai":
                    consol_config = config.CHAR_VALIDATOR_GPT52_NONE
                elif MODEL_PROVIDER == "gemini":
                    consol_config = config.CHAR_VALIDATOR_T054_GEMINI_FLASH_LOW
                elif MODEL_PROVIDER == "lmstudio":
                    consol_config = config.CHAR_VALIDATOR_LMSTUDIO
                else:  # legacy
                    consol_config = config.CHAR_VALIDATOR_LEGACY

                response = capture_and_fanout("T054", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": self.get_inventory_consolidation_system_prompt()},
                        {"role": "user", "content": consolidation_prompt}
                    ],
                    model=consol_config["model"],
                    temperature=0.1,
                    **{k: v for k, v in consol_config.items() if k != "model"})
                
                # Track usage if available
                if USAGE_TRACKING_AVAILABLE:
                    try:
                        from utils.openai_usage_tracker import get_global_tracker
                        tracker = get_global_tracker()
                        tracker.track(response, context={'endpoint': 'character_validation', 'purpose': 'validate_character_effects'})
                    except:
                        pass
                
                ai_response = response.choices[0].message.content.strip()
                
                # Parse AI response to get consolidation updates only
                consolidation_updates = self.parse_currency_consolidation_response(
                    ai_response,
                    consolidation_data,
                )
                
                if consolidation_updates:
                    # Apply updates using deep merge (same pattern as main character updater)
                    from updates.update_character_info import deep_merge_dict
                    corrected_data = deep_merge_dict(character_data, consolidation_updates)
                else:
                    # No consolidation needed
                    corrected_data = character_data

                # Cache only a successfully merged final state. A failed later
                # file write leaves a different source hash and therefore cannot
                # suppress a healing retry.
                final_currency_hash = self._compute_currency_hash(
                    self.extract_currency_consolidation_data(corrected_data)
                )
                self._update_currency_cache(character_name, final_currency_hash)
                return _validation_result(character_data, corrected_data)
                    
            except Exception as e:
                self.corrections_made = copy.deepcopy(corrections_before)
                self.logger.error(f"AI currency consolidation attempt {attempt} failed: {str(e)}")
                attempt += 1
                if attempt > max_attempts:
                    self.logger.error(f"All {max_attempts} currency consolidation attempts failed")
                    return _failed_validation_result(character_data, e)
        
        return _failed_validation_result(
            character_data,
            RuntimeError("T054 validation attempts exhausted"),
        )

    def ai_consolidate_inventory(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Backward-compatible data-only facade for T054."""

        return self.ai_consolidate_inventory_with_result(character_data).data
    
    def get_inventory_consolidation_system_prompt(self) -> str:
        """
        System prompt for AI inventory consolidation (currency and ammunition)
        
        Returns:
            System prompt with consolidation rules and examples
        """
        return """You are an expert inventory manager for the 5th edition of the world's most popular role playing game. Your job is to consolidate loose currency items and ammunition into their proper sections while preserving player agency over containers and valuables.

## PRIMARY TASKS: CURRENCY AND AMMUNITION CONSOLIDATION

You must:
1. Identify loose currency that should be added to the character's currency totals and remove those items from inventory
2. Identify ammunition items in equipment that should be moved to the ammunition section

### CONSOLIDATION RULES:

**DO CONSOLIDATE (add to currency and remove from inventory):**
- Loose coins with exact counts: "5 gold pieces", "10 silver", "30 copper"
- Emptied coin bags: "bag of 50 gold", "pouch with 100 silver"
- Clearly available counted currency: "20 gold from the table"
- Currency with clear amounts: "15 gp", "stack of 30 silver coins"

**DO NOT CONSOLIDATE (preserve as inventory items):**
- Gems/jewelry: "ruby worth 150 gold", "diamond (500gp value)", "golden necklace"
- Containers with contents: "chest containing 1000 gold", "locked strongbox with coins"
- Trapped/locked items: "trapped chest", "locked coffer", "sealed vault"
- Art objects: "golden statue worth 250gp", "ornate painting valued at 100gp"
- Trade goods: "silk worth 100gp", "rare spices (50gp value)"
- Ambiguous containers: Items where it's unclear if the player has opened them

### AMMUNITION CONSOLIDATION RULES:

**DO CONSOLIDATE (move to ammunition section and remove from equipment):**
- Clear ammunition items: "Arrows x 20", "Crossbow bolts x 10", "20 arrows"
- Ammunition with quantities: "Quiver with 30 arrows", "Bundle of 15 bolts"
- Only ammunition with an explicit numeric quantity (or a standard full container)

**DO NOT CONSOLIDATE (keep in equipment -- these are SPECIAL and must stay as inventory items):**
- Magical ammunition: "+1 arrows", "flaming arrows", "arrows of slaying", any item with "+" prefix
- Special ammunition: "silvered arrows", "adamantine bolts"
- CRITICAL: If an ammunition item name contains "+1", "+2", "+3", "flaming", "frost", "slaying", "silvered", "adamantine", or any other magical/special descriptor, it MUST remain in equipment. Do NOT move it to the ammunition section.
- Ammunition containers without clear count: "empty quiver", "bolt case"
- Non-standard ammunition: "ballista bolts", "special ammunition"

### AMMUNITION CONTAINER STANDARDIZATION:
**ALWAYS standardize container names:**
- "full quiver", "empty quiver", "quiver with 30 arrows" → "Quiver"
- "full bolt case", "empty bolt case", "bolt case with 20 crossbow bolts" → "Bolt case"

**If container is described as "full" or contains ammo:**
- Rename to standard name ("Quiver" or "Bolt case")
- Add appropriate ammunition to ammunition section:
  - "full quiver" → Add 20 arrows to ammunition
  - "quiver with 30 arrows" → Add 30 arrows to ammunition
  - "full bolt case" → Add 20 crossbow bolts to ammunition
  
**If container is explicitly "empty":**
- Rename to standard name but don't add ammunition

### CURRENCY TYPES:
- platinum (pp) = 10 gold
- gold (gp) = 1 gold
- electrum (ep) = 0.5 gold

IMPORTANT: Include ALL currency types that change in the output, including electrum and platinum if they change. Do not omit any denomination.
- silver (sp) = 0.1 gold  
- copper (cp) = 0.01 gold

### OUTPUT FORMAT:
Return a JSON object with ONLY the changes needed:
{
  "currency": {
    "gold": 125,
    "silver": 50
  },
  "ammunition": [
    {
      "name": "Arrows",
      "quantity": 20
    },
    {
      "name": "Crossbow bolt",
      "quantity": 50
    }
  ],
  "equipment": [
    {"item_name": "full quiver", "new_item_name": "Quiver", "_update": true},
    {"item_name": "Crossbow bolts x 10", "_remove": true},
    {"item_name": "5 gold pieces", "_remove": true}
  ],
  "consolidations_made": [
    "Consolidated X gold pieces into currency",
    "Emptied bag of Y gold into currency",
    "Total gold increased from A to B",
    "Renamed 'full quiver' to 'Quiver' and added 20 arrows",
    "Moved 'Crossbow bolts x 10' to ammunition section",
    "Ammunition 'Crossbow bolt' increased from 40 to 50"
  ]
}

CRITICAL: 
- Only return currency fields that changed
- Only return ammunition entries that changed
- Currency goes in the top-level "currency" object, never under "inventory"
- Every positive currency delta must exactly equal the explicit numeric currency in items listed with _remove=true
- Every positive ammunition delta must exactly equal the explicit numeric ammunition in items listed with _remove=true or a supported full-container rename
- Every value-bearing item that is removed must be fully represented in the matching currency or ammunition delta; never discard value
- A source item must contain only the currency or ammunition being consolidated; mixed-content items (for example, arrows plus a potion or coins plus a gem) must remain untouched
- A removal has exactly {"item_name": source name, "_remove": true}; _remove may never be false
- A container rename has exactly {"item_name": source name, "new_item_name": "Quiver" or "Bolt case", "_update": true}
- Never use _remove for a quiver or bolt case; preserve it with the supported rename directive, including when the canonical name is already unchanged
- Calculate new totals by adding consolidated amounts to existing currency/ammunition
- Every ammunition quantity is the absolute new total, never an amount-to-add delta
- Use standard ammunition names already present when possible
- Do not return ammunition descriptions; consolidation changes counts, not prose
- Preserve player agency - when in doubt, don't consolidate
- Word-only quantities such as "handful", "some", or "many" are ambiguous; do not consolidate them
- If names/descriptions contain conflicting quantities, do not consolidate them
- Trade goods with gold values (silk worth 100gp, rare spices) are NOT currency -- keep in inventory
- Locked, sealed, trapped, unopened, closed, or valuable containers MUST stay in inventory"""
    
    def build_inventory_consolidation_prompt(self, character_data: Dict[str, Any]) -> str:
        """
        Build consolidation prompt with character inventory
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Formatted prompt for AI consolidation
        """
        equipment = character_data.get('equipment', [])
        # Character sheets store currency at the top level. Keep a fallback for
        # older callers that may still provide the former nested shape.
        current_currency = character_data.get('currency')
        if not isinstance(current_currency, dict):
            current_currency = character_data.get('inventory', {}).get('currency', {})
        current_ammunition = character_data.get('ammunition', [])
        
        prompt = f"""Please consolidate loose currency and ammunition for this character:

CHARACTER NAME: {character_data.get('name', 'Unknown')}

CURRENT CURRENCY:
- Platinum: {current_currency.get('platinum', 0)}
- Gold: {current_currency.get('gold', 0)}
- Electrum: {current_currency.get('electrum', 0)}
- Silver: {current_currency.get('silver', 0)}
- Copper: {current_currency.get('copper', 0)}

CURRENT AMMUNITION:
"""
        for ammo in current_ammunition:
            prompt += f"- {ammo.get('name', 'Unknown')}: {ammo.get('quantity', 0)}\n"
        
        if not current_ammunition:
            prompt += "- None\n"
            
        prompt += """
CURRENT INVENTORY:
"""
        
        for i, item in enumerate(equipment):
            item_name = item.get('item_name', 'Unknown Item')
            item_type = item.get('item_type', 'Unknown')
            description = item.get('description', 'No description')
            quantity = item.get('quantity', 1)
            
            prompt += f"""
Item #{i+1}:
- Name: {item_name}
- Type: {item_type}
- Description: {description}
- Quantity: {quantity}
"""
        
        prompt += """

Identify loose currency items AND ammunition that should be consolidated. Remember:
- Consolidate loose coins and emptied bags into currency
- Move ammunition items (arrows, bolts) to the ammunition section
- Standardize container names (e.g., "full quiver" → "Quiver")
- If a container is "full", add ammo and rename container
- Preserve gems, containers, and valuables
- Calculate new totals after consolidation
- Return only the changes needed for both currency and ammunition"""
        
        return prompt
    
    def parse_currency_consolidation_response(self, ai_response: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AI currency consolidation response - returns only the updates/changes
        
        Args:
            ai_response: AI response string
            original_data: Original character data
            
        Returns:
            Dictionary with only the changes to apply (or empty dict if no changes)
        """
        parsed_response = _load_response_object(ai_response, "T054")
        recognized_fields = {
            'inventory', 'currency', 'ammunition', 'equipment',
            'consolidations_made',
        }
        unknown_fields = set(parsed_response).difference(recognized_fields)
        if unknown_fields:
            raise CharacterValidationResponseError(
                "T054: response contains unsupported field(s): "
                + ", ".join(sorted(unknown_fields))
            )
        if not recognized_fields.intersection(parsed_response):
            raise CharacterValidationResponseError(
                "T054: response contains no recognized consolidation fields"
            )
        for field in ('ammunition', 'equipment', 'consolidations_made'):
            if field in parsed_response and not isinstance(parsed_response[field], list):
                raise CharacterValidationResponseError(
                    f"T054: '{field}' must be an array"
                )
        if 'inventory' in parsed_response and not isinstance(
            parsed_response['inventory'], dict
        ):
            raise CharacterValidationResponseError(
                "T054: 'inventory' must be an object"
            )
        if 'currency' in parsed_response and not isinstance(
            parsed_response['currency'], dict
        ):
            raise CharacterValidationResponseError(
                "T054: 'currency' must be an object"
            )

        updates = {}
        source_currency = original_data.get('currency', {})
        if not isinstance(source_currency, dict):
            raise CharacterValidationResponseError(
                "T054: source currency must be an object"
            )
        source_equipment = _source_items_by_name(
            original_data.get('equipment', []),
            "T054: source equipment",
            reject_duplicates=True,
        )

        # First validate removal/rename directives. They are the authoritative
        # source side of the conservation equation and are never persisted.
        normalized_equipment = []
        removal_items = []
        rename_items = []
        seen_equipment = set()
        rename_destinations = set()
        for index, directive in enumerate(parsed_response.get('equipment', [])):
            if not isinstance(directive, dict):
                raise CharacterValidationResponseError(
                    f"T054: equipment[{index}] must be an object"
                )
            source_name = _normalized_name(directive.get('item_name'))
            if source_name not in source_equipment:
                raise CharacterValidationResponseError(
                    f"T054: equipment[{index}] must reference a source candidate"
                )
            if source_name in seen_equipment:
                raise CharacterValidationResponseError(
                    f"T054: duplicate equipment directive for '{directive.get('item_name')}'"
                )
            seen_equipment.add(source_name)
            source_item = source_equipment[source_name]

            if '_remove' in directive:
                if set(directive) != {'item_name', '_remove'}:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}] removal contains unsupported fields"
                    )
                if directive['_remove'] is not True:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}]._remove must be true"
                    )
                if _supported_container_rename(source_item) is not None:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}] must preserve and rename the "
                        "ammunition container instead of removing it"
                    )
                _require_destructively_safe_source_item(
                    source_item,
                    f"T054: equipment[{index}] source",
                )
                normalized_equipment.append({
                    'item_name': source_item['item_name'],
                    '_remove': True,
                })
                removal_items.append(source_item)
                continue

            if '_update' in directive:
                if set(directive) != {'item_name', 'new_item_name', '_update'}:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}] rename contains unsupported fields"
                    )
                if directive['_update'] is not True:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}]._update must be true"
                    )
                new_name = directive.get('new_item_name')
                if not isinstance(new_name, str) or not new_name.strip():
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}].new_item_name must be nonempty"
                    )
                normalized_new_name = _normalized_name(new_name)
                canonical_name = _supported_container_rename(source_item)
                if canonical_name == 'Quiver' and normalized_new_name == 'quiver':
                    canonical_description = 'A standard quiver for carrying arrows.'
                elif canonical_name == 'Bolt case' and normalized_new_name == 'bolt case':
                    canonical_description = 'A standard case for carrying crossbow bolts.'
                else:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}] is not a supported container rename"
                    )
                if normalized_new_name in rename_destinations:
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}] converges on duplicate rename "
                        f"destination '{canonical_name}'"
                    )
                rename_destinations.add(normalized_new_name)
                if (
                    normalized_new_name in source_equipment
                    and normalized_new_name != source_name
                ):
                    raise CharacterValidationResponseError(
                        f"T054: equipment[{index}] rename collides with existing equipment"
                    )
                # A model sometimes emits `Quiver -> Quiver` solely to move
                # its contents. Do not mark the same source row for deletion.
                consumed_update = _consumed_container_update(
                    source_item,
                    canonical_name,
                    canonical_description,
                )
                if source_item.get('item_name') != canonical_name:
                    replacement = copy.deepcopy(source_item)
                    replacement.update(consumed_update)
                    replacement.pop('_remove', None)
                    replacement.pop('_update', None)
                    replacement.pop('new_item_name', None)
                    normalized_equipment.extend([
                        {'item_name': source_item['item_name'], '_remove': True},
                        replacement,
                    ])
                else:
                    normalized_equipment.append(consumed_update)
                rename_items.append(source_item)
                continue

            raise CharacterValidationResponseError(
                f"T054: equipment[{index}] requires _remove=true or _update=true"
            )

        currency_source_items = []
        ammunition_source_items = []
        for index, source_item in enumerate(removal_items + rename_items):
            currency_evidence = _currency_evidence_from_item(
                source_item,
                f"T054: equipment source[{index}]",
            )
            ammo_evidence = _ammunition_evidence_from_item(
                source_item,
                f"T054: equipment source[{index}]",
            )
            if currency_evidence and ammo_evidence:
                raise CharacterValidationResponseError(
                    "T054 conservation source ambiguously contains currency and ammunition"
                )
            if currency_evidence:
                currency_source_items.append(source_item)
            elif ammo_evidence:
                ammunition_source_items.append(source_item)
            elif source_item in removal_items:
                raise CharacterValidationResponseError(
                    "T054 conservation cannot remove an item without unambiguous value"
                )

        # Normalize the legacy nested currency shape, but publish canonical
        # top-level currency only.
        inventory_updates = parsed_response.get('inventory')
        if isinstance(inventory_updates, dict):
            inventory_unknown = set(inventory_updates).difference({'currency'})
            if inventory_unknown:
                raise CharacterValidationResponseError(
                    "T054: inventory contains unsupported field(s): "
                    + ", ".join(sorted(inventory_unknown))
                )
        nested_currency = (
            inventory_updates.get('currency')
            if isinstance(inventory_updates, dict)
            else None
        )
        if nested_currency is not None and not isinstance(nested_currency, dict):
            raise CharacterValidationResponseError(
                "T054: inventory.currency must be an object"
            )
        top_level_currency = parsed_response.get('currency')
        if top_level_currency is not None and nested_currency is not None:
            raise CharacterValidationResponseError(
                "T054: currency must use one canonical location"
            )
        currency_updates = top_level_currency if top_level_currency is not None else nested_currency
        normalized_currency = {}
        currency_deltas = {}
        if currency_updates is not None:
            unknown_currency = set(currency_updates).difference(VALID_CURRENCY_FIELDS)
            if unknown_currency:
                raise CharacterValidationResponseError(
                    "T054: currency contains unsupported denomination(s): "
                    + ", ".join(sorted(unknown_currency))
                )
            for denomination, value in currency_updates.items():
                new_total = _require_contract_integer(
                    value,
                    f"T054: currency.{denomination}",
                    minimum=0,
                )
                current_total = _require_contract_integer(
                    source_currency.get(denomination, 0),
                    f"T054: source currency.{denomination}",
                    minimum=0,
                )
                if new_total < current_total:
                    raise CharacterValidationResponseError(
                        f"T054: currency.{denomination} may not decrease during consolidation"
                    )
                if new_total != current_total:
                    normalized_currency[denomination] = new_total
                    currency_deltas[denomination] = new_total - current_total

        currency_evidence = _aggregate_evidence(
            currency_source_items,
            _currency_evidence_from_item,
            "T054: currency sources",
        )
        _require_exact_conservation(
            "T054 currency",
            currency_deltas,
            currency_evidence,
        )
        if normalized_currency:
            updates['currency'] = normalized_currency

        # Provider ammunition values are absolute totals. Convert only after
        # proving their positive deltas exactly match removed source quantities.
        current_ammunition = {}
        source_ammunition_rows = original_data.get('ammunition', [])
        _require_unique_source_ammunition(
            source_ammunition_rows,
            "T054: source ammunition",
        )
        for source_index, source_ammo in enumerate(source_ammunition_rows):
            if not isinstance(source_ammo, dict):
                raise CharacterValidationResponseError(
                    f"T054: source ammunition[{source_index}] must be an object"
                )
            canonical_name = _canonical_ammunition_name(source_ammo.get('name'))
            if canonical_name is None:
                continue
            amount = _require_contract_integer(
                source_ammo.get('quantity', 0),
                f"T054: source ammunition[{source_index}].quantity",
                minimum=0,
            )
            entry = current_ammunition.setdefault(
                canonical_name,
                {'name': source_ammo.get('name'), 'quantity': 0},
            )
            entry['quantity'] += amount

        ammunition_updates = []
        ammunition_deltas = {}
        seen_ammunition = set()
        for index, ammo in enumerate(parsed_response.get('ammunition', [])):
            if not isinstance(ammo, dict) or set(ammo).difference(
                {'name', 'quantity', 'description'}
            ):
                raise CharacterValidationResponseError(
                    f"T054: ammunition[{index}] is invalid"
                )
            canonical_name = _canonical_ammunition_name(ammo.get('name'))
            if canonical_name is None or canonical_name in seen_ammunition:
                raise CharacterValidationResponseError(
                    f"T054: ammunition[{index}] requires a unique standard name"
                )
            seen_ammunition.add(canonical_name)
            current_entry = current_ammunition.get(canonical_name, {})
            current_total = _require_contract_integer(
                current_entry.get('quantity', 0),
                f"T054: source ammunition[{canonical_name}].quantity",
                minimum=0,
            )
            new_total = _require_contract_integer(
                ammo.get('quantity'),
                f"T054: ammunition[{index}].quantity",
                minimum=0,
            )
            if new_total < current_total:
                raise CharacterValidationResponseError(
                    f"T054: ammunition total for '{ammo.get('name')}' may not decrease"
                )
            delta_amount = new_total - current_total
            if delta_amount:
                normalized_ammo = copy.deepcopy(ammo)
                normalized_ammo['name'] = current_entry.get(
                    'name',
                    ammo['name'].strip(),
                )
                normalized_ammo['quantity'] = delta_amount
                normalized_ammo.pop('description', None)
                ammunition_updates.append(normalized_ammo)
                ammunition_deltas[canonical_name] = delta_amount

        ammunition_evidence = _aggregate_evidence(
            ammunition_source_items,
            _ammunition_evidence_from_item,
            "T054: ammunition sources",
        )
        _require_exact_conservation(
            "T054 ammunition",
            ammunition_deltas,
            ammunition_evidence,
        )
        if ammunition_updates:
            updates['ammunition'] = ammunition_updates
        if normalized_equipment:
            updates['equipment'] = normalized_equipment

        consolidations = _require_string_list(
            parsed_response.get('consolidations_made', []),
            "T054: 'consolidations_made'",
        )
        for consolidation in consolidations:
            print(f"DEBUG: [Consolidation] {consolidation}")
            info(f"[Consolidation] {consolidation}", category="character_validation")
            self.logger.info(f"AI Currency Consolidation: {consolidation}")
            self.corrections_made.append(consolidation)

        return updates if updates else {}
    
    def ensure_currency_integrity(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure currency object has all required fields (gold, silver, copper).
        This prevents KeyError crashes when fields are missing.
        
        Args:
            character_data: Character data to validate
            
        Returns:
            Character data with complete currency object
        """
        if 'currency' not in character_data:
            character_data['currency'] = {}
        
        currency = character_data['currency']
        
        # Ensure all currency fields exist with default value of 0
        required_fields = ['gold', 'silver', 'copper']
        missing_fields = []
        
        for field in required_fields:
            if field not in currency:
                currency[field] = 0
                missing_fields.append(field)
        
        if missing_fields:
            print(f"DEBUG: [Currency Integrity] Added missing currency fields: {missing_fields}")
            info(f"[Currency Integrity] Added missing currency fields: {missing_fields}", category="character_validation")
            self.corrections_made.append(f"Added missing currency fields: {', '.join(missing_fields)}")
        
        return character_data
    
    def consolidate_ammunition(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Safely consolidate compatible rows of standard ammunition.

        A row is eligible only when it has a canonical standard-ammunition name
        and an exact, non-negative integer quantity.  Rows are merged only when
        every other field is exactly equal (including value types).  All
        malformed, blank, special, or metadata-distinct rows remain untouched.

        Args:
            character_data: Character data to validate

        Returns:
            Character data with consolidated ammunition
        """
        if not isinstance(character_data, dict):
            return character_data
        ammunition_list = character_data.get('ammunition')
        if not isinstance(ammunition_list, list):
            return character_data
        if len(ammunition_list) <= 1:
            return character_data

        # Preserve input order.  A group points at the first compatible row;
        # only that standard row is copied and changed when a later match is
        # actually found.  Ineligible rows are neither keyed nor rebuilt.
        consolidated_rows = list(ammunition_list)
        groups = []
        removed_indices = set()
        merge_descriptions = []

        for index, ammo in enumerate(ammunition_list):
            if not isinstance(ammo, dict):
                continue
            canonical_name = _canonical_ammunition_name(ammo.get('name'))
            quantity = ammo.get('quantity')
            if (
                canonical_name is None
                or type(quantity) is not int
                or quantity < 0
            ):
                continue

            metadata = {
                key: value
                for key, value in ammo.items()
                if key not in {'name', 'quantity'}
            }
            compatible_group = next(
                (
                    group for group in groups
                    if group['canonical_name'] == canonical_name
                    and _exact_metadata_equal(group['metadata'], metadata)
                ),
                None,
            )
            if compatible_group is None:
                groups.append({
                    'canonical_name': canonical_name,
                    'metadata': metadata,
                    'output_index': index,
                    'quantity': quantity,
                    'source_names': [ammo.get('name')],
                })
                continue

            output_index = compatible_group['output_index']
            compatible_group['quantity'] += quantity
            compatible_group['source_names'].append(ammo.get('name'))
            merged_row = dict(consolidated_rows[output_index])
            merged_row['name'] = canonical_name.title()
            merged_row['quantity'] = compatible_group['quantity']
            consolidated_rows[output_index] = merged_row
            removed_indices.add(index)

        if removed_indices:
            consolidated_rows = [
                ammo
                for index, ammo in enumerate(consolidated_rows)
                if index not in removed_indices
            ]
            for group in groups:
                if len(group['source_names']) > 1:
                    source_names = ' + '.join(
                        str(name) for name in group['source_names']
                    )
                    merge_descriptions.append(
                        f"{source_names} -> {group['canonical_name'].title()} "
                        f"({group['quantity']})"
                    )

            character_data['ammunition'] = consolidated_rows
            print(
                "DEBUG: [Ammunition Consolidation] Consolidated "
                f"{len(ammunition_list)} entries to {len(consolidated_rows)}"
            )
            info(
                "[Ammunition Consolidation] Consolidated compatible duplicate "
                "ammunition entries",
                category="character_validation",
            )
            self.corrections_made.append(
                "Consolidated ammunition: " + "; ".join(merge_descriptions)
            )

        return character_data


def validate_character_file(file_path: str) -> bool:
    """
    Convenience function to validate a character file using AI with atomic file operations
    
    CRITICAL: This function ensures currency fields are never erased by:
    1. Using safe_write_json which creates automatic .bak backups
    2. Merging currency updates instead of replacing
    3. Validating currency object has all required fields
    
    Args:
        file_path: Path to character JSON file
        
    Returns:
        True if validation successful, False otherwise
    """
    try:
        # Load character data using safe file operations
        character_data = safe_read_json(file_path)
        if character_data is None:
            error(f"FAILURE: Could not read character file {file_path}", category="file_operations")
            return False
        
        # AI validation and correction
        validator = AICharacterValidator()
        corrected_data = validator.validate_and_correct_character(character_data)
        
        # Save if corrections were made using atomic file operations
        if validator.corrections_made:
            success = safe_write_json(file_path, corrected_data)
            if success:
                info(f"SUCCESS: AI Corrections made: {validator.corrections_made}", category="character_validation")
                return True
            else:
                error(f"FAILURE: Failed to save corrected character data to {file_path}", category="file_operations")
                return False
        else:
            debug("VALIDATION: No corrections needed - character data is valid", category="character_validation")
            return True
        
    except Exception as e:
        error(f"FAILURE: Error validating character file {file_path}", exception=e, category="character_validation")
        return False


if __name__ == "__main__":
    # Test with character file
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        validate_character_file(file_path)
    else:
        # Test with default character
        validate_character_file("modules/Keep_of_Doom/characters/norn.json")
