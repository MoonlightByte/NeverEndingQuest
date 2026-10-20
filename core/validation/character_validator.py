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
import jsonschema
from core.nql import item_catalog
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from core.ai import api_client
from utils.character_sheet_contract import repair_required_ammunition_field
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T051", "core/validation/character_validator.py", 1412)
register_callsite("T052", "core/validation/character_validator.py", 1603)
register_callsite("T054", "core/validation/character_validator.py", 2547)

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
                "base_ac",
                "dex_modifier",
                "shield_bonus",
                "fighting_style_bonus",
                "total_ac",
            ],
            "properties": {
                "base_armor": {"type": "string"},
                "base_ac": {"type": ["string", "integer", "number"]},
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
_DESTRUCTIVE_SOURCE_BASE_FIELDS = frozenset({
    "item_name",
    "catalog_id",
    "item_type",
    "nql_id",
    "description",
    "quantity",
    "equipped",
    "magical",
    "item_subtype",
})


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
    if item.get("item_subtype") not in (None, "", "other"):
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


def _catalog_ammunition() -> Dict[str, Dict[str, Any]]:
    """The catalog's ammunition entries by casefolded name: the closed list T054 names from."""
    return {
        entry["name"].casefold(): entry
        for entry in item_catalog.entries().values()
        if entry.get("kind") == "ammunition" and isinstance(entry.get("name"), str)
    }


def _typed_ammunition_row(item: Dict[str, Any]) -> bool:
    """An equipment row typed as ammunition: its catalog_id names a catalog
    ammunition entry, or, without a catalog entry, its item_type is ammunition."""
    found = item_catalog.entry(item.get("catalog_id"))
    if found is not None:
        return found.get("kind") == "ammunition"
    item_type = item.get("item_type")
    return isinstance(item_type, str) and item_type.strip().casefold() == "ammunition"


def _row_catalog_ammunition(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The catalog ammunition an equipment row is: its catalog_id, else its
    exact catalog or #552 legacy name (item_catalog.ammunition_entry), else None."""
    return item_catalog.ammunition_entry({"name": item.get("item_name"), "catalog_id": item.get("catalog_id")})


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


# The six equipment fields the T051 armor agent may change. Every value the
# model proposes, every merged result, every cache hit and every source sheet
# offered to T051 is checked against the frozen character schema's letter for
# these fields only (issue #357: hand-written guards rejected the schema-valid
# null echo, the model then invented 99, and the poisoned sheet blocked later
# updates while its cache entry vouched for it).
_T051_ARMOR_FIELDS = (
    'equipped', 'ac_base', 'ac_bonus', 'dex_limit',
    'armor_category', 'stealth_disadvantage',
)
# A row carrying any of these is an armor row for T051 and the contract check,
# whatever its name or item_type says.
_ARMOR_ROW_FIELDS = _T051_ARMOR_FIELDS[1:]


def malformed_armor_entry(item: Dict[str, Any]) -> bool:
    """An entry typed armor with neither armor_category nor an integer ac_base.

    Such an entry is not modelled armor (the engine gives it no defense) and
    is the one case in which the T051 field agent may change item_type.
    """
    return (
        isinstance(item, dict)
        and item.get('item_type') == 'armor'
        and item.get('armor_category') is None
        and type(item.get('ac_base')) is not int
    )


def armor_contract_errors(
    items: List[Dict[str, Any]],
    item_schema: Dict[str, Any],
) -> List[str]:
    """Return one message per present armor field outside the frozen schema.

    ``item_schema`` is the character schema's equipment item subschema. Only the
    schema's letter (type, enum, range, null-ness) is checked; which value is
    right for an armor stays with the model. An empty list means every present
    armor field is schema-valid.
    """
    errors: List[str] = []
    field_schemas = item_schema['properties']
    for item in items:
        if malformed_armor_entry(item):
            errors.append(
                f"equipment '{item.get('item_name')}' is typed armor but carries no "
                "armor_category and no ac_base; it must be classified: body armor or a "
                "shield gets armor_category and ac_base, anything else is not item_type armor"
            )
        for field in _T051_ARMOR_FIELDS:
            if field not in item:
                continue
            subschema = field_schemas[field]
            validator = jsonschema.Draft7Validator(subschema)
            for schema_error in validator.iter_errors(item[field]):
                errors.append(
                    f"equipment '{item.get('item_name')}'.{field} "
                    f"{schema_error.message}; the character schema for {field} "
                    f"is {json.dumps(subschema, sort_keys=True)}"
                )
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
from utils.capture.live_provider_call import LiveProviderSuperseded, LiveProviderUnavailable
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

class AICharacterValidator:
    def __init__(self, *, commit_guard=None, provider_scope=None, persist_cache=True,
                 provider_status=None):
        """Initialize AI-powered validator with caching"""
        self.commit_guard = commit_guard
        self.provider_scope = provider_scope
        # Optional caller-owned status sink for provider heartbeats (level-up
        # phase reporting); None keeps the ordinary global transport status.
        self.provider_status = provider_status
        self.persist_cache = persist_cache
        self.logger = logging.getLogger(__name__)
        self.corrections_made = []
        
        # Load prompts from external files
        self.ac_prompt = self._load_prompt('character_validator_ac.txt')
        self.inventory_prompt = self._load_prompt('character_validator_inventory.txt')
        
        # Initialize validation cache
        self.cache_file = os.path.join('modules', 'validation_cache.json')
        self.validation_cache = self._load_cache()
        # Frozen equipment item subschema, read lazily from the writer's schema file
        self._equipment_item_schema_cache = None
    
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
    
    def _equipment_item_schema(self) -> Dict[str, Any]:
        """Equipment item subschema from the same schemas/char_schema.json the writer loads."""
        if self._equipment_item_schema_cache is None:
            from updates.update_character_info import load_schema
            try:
                item_schema = load_schema()['properties']['equipment']['items']
                item_schema['properties']
            except Exception as exc:
                raise RuntimeError(
                    "T051: could not read properties.equipment.items.properties "
                    f"from schemas/char_schema.json: {exc}"
                ) from exc
            self._equipment_item_schema_cache = item_schema
        return self._equipment_item_schema_cache

    def extract_ac_relevant_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only the fields relevant for AC validation.
        This dramatically reduces token usage from ~7800 to ~500-800.
        
        Includes:
        - Core context (class, race) and the ability scores AC reads
        - Equipment effects whose typed target is armor class
        - The armor rows (typed armor or any armor field), with their index
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
        
        # Equipment effects the engine attributes to armor class (typed target).
        from core.nql.armor_class import AC_TARGET

        equipment_effects = character_data.get('equipment_effects', [])
        ac_equipment_effects = [
            effect for effect in equipment_effects
            if isinstance(effect, dict) and effect.get('target') == AC_TARGET
        ]
        
        if ac_equipment_effects:
            ac_data['equipment_effects'] = ac_equipment_effects
        
        # The armor rows: typed armor, or any armor field present. Each keeps
        # its equipment index, which a T051 answer names. Armor class itself is
        # the engine's (armor_class.project), so no class feature, trait or
        # feat text is offered.
        equipment = character_data.get('equipment', [])
        ac_relevant_equipment = []
        
        for index, item in enumerate(equipment):
            if not isinstance(item, dict):
                continue
            typed_armor = str(item.get('item_type', '')).strip().lower() == 'armor'
            if not typed_armor and not any(field in item for field in _ARMOR_ROW_FIELDS):
                continue
            item_data = {
                'row': index,
                'item_name': item.get('item_name'),
                'item_type': item.get('item_type'),
                'equipped': item.get('equipped', False),
                'description': item.get('description', '')[:200]  # Limit description length
            }
            for field in _ARMOR_ROW_FIELDS:
                if field in item:
                    item_data[field] = item[field]
            ac_relevant_equipment.append(item_data)
        
        ac_data['equipment'] = ac_relevant_equipment
        
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
        
        return ac_data
    
    def extract_inventory_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the rows T052 types: the typed focus, never a word list.

        A row whose item_type is not a schema type is always offered. With a
        pre-write sheet (check_validation_needs), so is a row the write
        introduced (_entries_needing_typing) with the catch-all type
        "miscellaneous"; a row its writer gave any other schema type keeps it
        (owner, keyword validation V2). A catalog row is typed by its pack
        entry and is never offered. Each row keeps its equipment index, which
        the answer names.

        Args:
            character_data: Full character JSON data

        Returns:
            The offered rows with their equipment index
        """
        inventory_data = {
            'name': character_data.get('name', 'Unknown'),
            'equipment': []
        }

        equipment = character_data.get('equipment', [])
        if not isinstance(equipment, list):
            return inventory_data
        focus_names = getattr(self, '_focus_names', None)
        for index, item in enumerate(equipment):
            if not isinstance(item, dict):
                continue
            if item_catalog.row_entry(item)[0] is not None:
                continue
            item_type = str(item.get('item_type', '')).strip().lower()
            include = item_type not in VALID_INVENTORY_ITEM_TYPES
            if focus_names is not None:
                # D-COST-7 (#193): a new row the schema already accepts, miscellaneous included, is not
                # re-typed; only a row without a valid item_type reaches T052.
                include = str(item.get('item_name')) in focus_names and include
            if include:
                inventory_data['equipment'].append({
                    'row': index,
                    'item_name': item.get('item_name'),
                    'item_type': item.get('item_type'),
                    'description': str(item.get('description', ''))[:150],
                    'quantity': item.get('quantity', 1)
                })

        debug(f"[Inventory Extraction] {len(inventory_data['equipment'])} of {len(equipment)} equipment rows offered to T052", category="character_validation")

        return inventory_data
    
    def extract_currency_consolidation_data(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the rows T054 decides on: equipment rows typed as ammunition.

        A row is offered only when its typed facts let the engine remove it: a
        catalog ammunition id or item_type ammunition, a whole quantity of at
        least 1, no metadata a removal would discard, and a name no other
        equipment row shares (the engine removes rows by name). Names and
        descriptions are shown to the model; code does not read them.

        Args:
            character_data: Full character JSON data

        Returns:
            The sheet's ammunition stocks and the offered rows with their
            equipment index
        """
        consolidation_data = {
            'name': character_data.get('name', 'Unknown'),
            'ammunition': character_data.get('ammunition', []),
            'equipment': []
        }

        equipment = character_data.get('equipment', [])
        if not isinstance(equipment, list) or not _catalog_ammunition():
            return consolidation_data
        name_counts = {}
        for item in equipment:
            if isinstance(item, dict):
                name_counts[item.get('item_name')] = name_counts.get(item.get('item_name'), 0) + 1
        focus_names = getattr(self, '_focus_names', None)
        for index, item in enumerate(equipment):
            if not isinstance(item, dict) or not _typed_ammunition_row(item):
                continue
            if focus_names is not None and str(item.get('item_name')) not in focus_names:
                continue
            if not isinstance(item.get('item_name'), str) or name_counts[item['item_name']] != 1:
                continue
            if type(item.get('quantity')) is not int or item['quantity'] < 1:
                continue
            try:
                _require_destructively_safe_source_item(item, "T054 extraction")
            except CharacterValidationResponseError:
                continue
            consolidation_data['equipment'].append({'row': index, 'item': copy.deepcopy(item)})

        debug(f"[Ammunition Extraction] {len(consolidation_data['equipment'])} of {len(equipment)} equipment rows typed as ammunition offered to T054", category="character_validation")

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
        if not self.persist_cache:
            return
        try:
            safe_write_json(self.cache_file, self.validation_cache, commit_guard=self.commit_guard)
            debug(f"[Validation Cache] Saved cache with {len(self.validation_cache)} entries", category="character_validation")
        except Exception as e:
            if self.commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                raise
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
    
    def _is_ac_validation_cached(
        self,
        character_name: str,
        ac_hash: str,
        ac_data: Dict[str, Any],
    ) -> bool:
        """
        Check if AC validation is cached and still valid
        
        Args:
            character_name: Name of the character
            ac_hash: Hash of current AC-relevant data
            ac_data: AC-relevant projection the hash was computed from
            
        Returns:
            True if cached, unchanged and schema-valid, False otherwise
        """
        if character_name not in self.validation_cache:
            return False
        
        cache_entry = self.validation_cache[character_name]
        
        # Check if AC data has changed
        if cache_entry.get('ac_hash') != ac_hash:
            debug(f"[Validation Cache] AC data changed for {character_name}", category="character_validation")
            return False
        
        # A cache entry may vouch only for armor values that are actually inside
        # the frozen schema; a poisoned projection never hits (issue #357).
        armor_errors = armor_contract_errors(
            ac_data['equipment'], self._equipment_item_schema()
        )
        if armor_errors:
            warning(
                f"[Validation Cache] Cached AC projection for {character_name} is "
                f"outside the character schema; revalidating: {armor_errors}",
                category="character_validation",
            )
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
        before: Optional[Dict[str, Any]] = None,
        max_attempts: Optional[int] = None,
    ) -> CharacterValidationResult:
        """One validation entry for every caller (E7).

        The combined three-task call (T053) is retired: armor class is the
        engine's, and categorization and consolidation run only for entries a
        write introduced or left untyped when ``before`` is supplied. Callers
        without a pre-write sheet keep the content-cache gate.
        """
        return self.validate_and_correct_character_smart_with_result(
            character_data, before=before, max_attempts=max_attempts,
        )

    def validate_and_correct_character(
        self,
        character_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Backward-compatible data-only facade for full validation."""

        return self.validate_and_correct_character_with_result(character_data).data
    
    def _name_legacy_features(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """T125 once for legacy classFeatures names a table lookup misses; journaled.
        A failed naming leaves the sheet unchanged and is asked again next time."""
        from core.leveling import feature_names

        named = feature_names.name_features(
            character_data, scope=self.provider_scope, status=self.provider_status,
            live_selected='advisory' if self.provider_scope is not None else None)
        self.corrections_made.extend(named.notes)
        return named.sheet

    def _raise_pools_to_tables(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """Raise use pool and spell slot maxima below the SRD class table (#704); journaled."""
        from core.leveling import tables

        raised = copy.deepcopy(character_data)
        notes = tables.raise_to_tables(raised)
        if not notes:
            return character_data
        name = character_data.get('name', 'Unknown')
        for note in notes:
            self.corrections_made.append(note)
            info(f"[Pool Tables] {name}: {note}", category="character_validation")
        return raised

    def _project_armor_class(self, character_data: Dict[str, Any]) -> Dict[str, Any]:
        """Rewrite armorClass and the AC entries of equipment_effects from the
        engine's defense explanation. Unchanged data on any failure (logged)."""
        from core.nql import armor_class

        projection = armor_class.project(character_data)
        name = character_data.get('name', 'Unknown')
        if not projection.applied:
            warning(f"[AC Projection] {name}: sheet left unchanged: {projection.reason}",
                    category="character_validation")
            return character_data
        for note in projection.notes:
            info(f"[AC Projection] {name}: {note}", category="character_validation")
        if projection.changed:
            self.corrections_made.append(
                f"armorClass {projection.previous_armor_class} -> {projection.armor_class} (engine explanation)")
            info(f"[AC Projection] {name}: armorClass {projection.previous_armor_class} -> {projection.armor_class}",
                 category="character_validation")
        return projection.sheet

    def _entries_needing_typing(self, before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Equipment entries the write introduced or left untyped (typed facts only).

        An entry is new when its nql_id was not on the sheet before, or, for an
        entry that has no id yet, when no entry of that item_name was. An entry
        is untyped when its item_type is not one the schema lists. Nothing
        else on the sheet asks the categorization or consolidation models for
        an opinion (E7).
        """
        before_ids = set()
        before_names = set()
        for entry in before.get('equipment') or []:
            if isinstance(entry, dict):
                if isinstance(entry.get('nql_id'), str):
                    before_ids.add(entry['nql_id'])
                before_names.add(str(entry.get('item_name', '')))
        focus = []
        for entry in after.get('equipment') or []:
            if not isinstance(entry, dict) or not entry.get('item_name'):
                continue
            if item_catalog.row_entry(entry)[0] is not None:
                continue  # SA: a catalog row is typed by its pack entry; nothing to classify
            nql_id = entry.get('nql_id')
            is_new = (nql_id not in before_ids) if isinstance(nql_id, str) else (str(entry['item_name']) not in before_names)
            untyped = str(entry.get('item_type', '')).lower() not in VALID_INVENTORY_ITEM_TYPES
            if is_new or untyped:
                focus.append(entry)
        return focus

    def check_validation_needs(self, character_data: Dict[str, Any], before: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
        """
        Check which validations actually need API calls (not cached)
        
        Args:
            character_data: Character JSON data
            
        Returns:
            Dictionary indicating which validations need API calls
        """
        character_name = character_data.get('name', 'Unknown')
        # With the pre-write sheet in hand, only entries the write introduced
        # or left untyped are offered to the models; a storage move, a payment
        # or a coin handoff offers none and makes no call.
        self._focus_names = None
        if before is not None:
            self._focus_names = {str(e.get('item_name')) for e in self._entries_needing_typing(before, character_data)}
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
        
        # Armor class is engine-owned: the projection is a local call with no
        # provider cost, so it always runs (a stale cache entry must never keep
        # a wrong number on the sheet). The AC hash cache is no longer consulted.
        needs_validation['ac'] = True
        
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
        before: Optional[Dict[str, Any]] = None,
        max_attempts: Optional[int] = None,
    ) -> CharacterValidationResult:
        """
        Smart validation that only calls validators that need updates

        Args:
            character_data: Character JSON data

        Returns:
            AI-corrected character data
        """
        if self.commit_guard is not None:
            with self.commit_guard():
                pass
        character_name = character_data.get('name', 'Unknown')
        info(f"[Smart Validator] Checking {character_name} for needed validations...", category="character_validation")
        original_snapshot = copy.deepcopy(character_data)

        # Check what needs validation
        needs = self.check_validation_needs(original_snapshot, before=before)

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

        # Use pools and spell slots below the class table for the hero's level
        # are raised (never lowered, current untouched) before the projection,
        # so genesis declares them at their table maximum (#704).
        # A legacy feature name the SRD tables miss ("Channel Divinity (2/rest)")
        # is named once by T125 as a typed srd_name, so the pools below and
        # level-up find it without cutting the name (keyword validation V4).
        corrected_data = self._name_legacy_features(corrected_data)
        corrected_data = self._raise_pools_to_tables(corrected_data)

        if needs['ac']:
            # Armor class is engine-owned (core/nql): the engine explains
            # defense from the sheet's typed fields and code writes the number.
            # T051 is no longer asked; an unapplied projection leaves the sheet
            # as it was and is logged, never handed to a model to guess.
            corrected_data = self._project_armor_class(corrected_data)
        
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
        if self.commit_guard is not None:
            with self.commit_guard():
                pass
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
        if self._is_ac_validation_cached(character_name, ac_hash, ac_relevant_data):
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
        strict = self.provider_scope is not None and self.provider_scope.completion_required
        base_messages = list(messages)
        last_candidate = None
        attempt = 0
        while True:
            ai_response = None
            if not strict:
                attempt += 1
            if strict:
                messages = list(base_messages)
                if last_candidate is not None:
                    raw, objection = last_candidate
                    messages.extend([
                        {"role": "assistant", "content": raw if isinstance(raw, str) else ""},
                        {"role": "user", "content": (
                            f"VALIDATION ERROR: {objection}. Return the complete JSON "
                            "object again. Ensure validated_character_data.armorClass "
                            "exactly equals ac_calculation_breakdown.total_ac, that total_ac "
                            "equals base_ac + dex_modifier + shield_bonus + "
                            "fighting_style_bonus (all integers), and that "
                            "corrections_made accurately describes any changed value.")},
                    ])
            try:
                response = capture_and_fanout("T051", api_client.create_completion,
                    _detached_scope=self.provider_scope,
                    _detached_status=self.provider_status,
                    _live_selected='advisory' if self.provider_scope is not None else None,
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

                ai_response = response.choices[0].message.content
                if not strict:
                    ai_response = ai_response.strip()

                # Parse AI response to get corrected character data
                corrected_data = self.parse_ai_validation_response(
                    ai_response,
                    provider_ac_data,
                )

                # Each equipment correction names its row; two rows with one
                # name are two rows.
                merged_data = copy.deepcopy(character_data)
                merged_data['armorClass'] = corrected_data['armorClass']
                for update in corrected_data.get('equipment', []):
                    target = merged_data['equipment'][update['row']]
                    for field, value in update.items():
                        if field != 'row':
                            target[field] = copy.deepcopy(value)

                # The merged projection, not just the fields the model returned,
                # must satisfy the frozen schema: an omitted poisoned item would
                # otherwise survive the changed-only merge and be blessed here.
                merged_ac_data = self.extract_ac_relevant_data(merged_data)
                merged_errors = armor_contract_errors(
                    merged_ac_data['equipment'], self._equipment_item_schema()
                )
                if merged_errors:
                    raise CharacterValidationResponseError(
                        "T051: the merged equipment still violates the character "
                        "schema: " + "; ".join(merged_errors) + ". Return each "
                        "listed item in validated_character_data.equipment with a "
                        "schema-valid value and describe the change in "
                        "corrections_made"
                    )

                # Cache the fully merged output, never the pre-correction input. If a
                # later persistence step fails, the unchanged disk data will not hit
                # this entry and validation will self-heal on the next pass.
                final_ac_hash = self._compute_ac_hash(merged_ac_data)
                self._update_ac_cache(character_name, final_ac_hash, merged_data)

                return _validation_result(character_data, merged_data)
            except Exception as e:
                if self.commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                    raise
                self.corrections_made = copy.deepcopy(corrections_before)
                if strict:
                    if isinstance(e, LiveProviderUnavailable) and e.envelope.get('disposition') == 'empty':
                        continue
                    if isinstance(e, CharacterValidationResponseError):
                        last_candidate = (ai_response, str(e))
                        continue
                    raise
                last_error = e
                self.logger.error(
                    f"AI validation failed (attempt {attempt}/{max_attempts}): {e}"
                )
                if attempt >= max_attempts:
                    break
                if ai_response is not None:
                    messages.extend([
                        {"role": "assistant", "content": ai_response},
                        {
                            "role": "user",
                            "content": (
                                f"VALIDATION ERROR: {e}. Return the complete JSON "
                                "object again. Ensure validated_character_data.armorClass "
                                "exactly equals ac_calculation_breakdown.total_ac, that total_ac "
                            "equals base_ac + dex_modifier + shield_bonus + "
                            "fighting_style_bonus (all integers), and that "
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
        strict = self.provider_scope is not None and self.provider_scope.completion_required
        last_candidate = None
        
        max_attempts = 3
        attempt = 1
        corrections_before = copy.deepcopy(self.corrections_made)
        
        while strict or attempt <= max_attempts:
            ai_response = None
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

                messages = [
                    {"role": "system", "content": self.get_inventory_validator_system_prompt()},
                    {"role": "user", "content": validation_prompt}
                ]
                if last_candidate is not None:
                    raw, objection = last_candidate
                    messages.extend([
                        {"role": "assistant", "content": raw if isinstance(raw, str) else ""},
                        {"role": "user", "content": (
                            "Your last response failed this validator's contract: " + objection
                            + ". Return the complete JSON object required by the unchanged system "
                              "and user instructions. Correct the stated defect and preserve valid fields.")},
                    ])
                response = capture_and_fanout("T052", api_client.create_completion,
                    _detached_scope=self.provider_scope,
                    _detached_status=self.provider_status,
                    _live_selected='advisory' if self.provider_scope is not None else None,
                    _request_provider=MODEL_PROVIDER,
                    messages=messages,
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
                
                ai_response = response.choices[0].message.content
                if not strict:
                    ai_response = ai_response.strip()
                
                # Each correction names its equipment row; two rows with one
                # name are two rows.
                retyped = self.parse_inventory_validation_response(
                    ai_response,
                    inventory_data,
                )
                
                if retyped:
                    corrected_data = copy.deepcopy(character_data)
                    for row, item_type in retyped:
                        corrected_data['equipment'][row]['item_type'] = item_type
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
                if self.commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                    raise
                self.corrections_made = copy.deepcopy(corrections_before)
                if strict:
                    if isinstance(e, LiveProviderUnavailable) and e.envelope.get('disposition') == 'empty':
                        continue
                    if isinstance(e, CharacterValidationResponseError):
                        last_candidate = (ai_response, str(e))
                        continue
                    raise
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
        # The breakdown's integer parts must add up to total_ac, so the number
        # written to the sheet is tied to the arithmetic the model showed
        # (mirrors the T053 check; a string breakdown let 14+1+2 be accepted as 18).
        parts_total = 0
        for part in ('base_ac', 'dex_modifier', 'shield_bonus', 'fighting_style_bonus'):
            parts_total += _require_contract_integer(
                breakdown[part],
                f"T051: ac_calculation_breakdown.{part}",
            )
        if breakdown_total != parts_total:
            raise CharacterValidationResponseError(
                "T051: breakdown total_ac must equal the sum of its parts"
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
            source_equipment = {
                entry['row']: entry for entry in original_data.get('equipment', [])
            }
            seen_rows = set()
            immutable_equipment_fields = {'item_name', 'item_type', 'description', 'quantity'}
            # A malformed armor entry (typed armor, no armor fields) may be
            # reclassified by the model to a non-armor type; every other
            # entry keeps its item_type.
            reclassifiable = {
                row for row, entry in source_equipment.items()
                if malformed_armor_entry(entry)
            }
            allowed_equipment_fields = {
                'row', 'item_name', 'item_type', 'equipped', 'description',
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
                row = item.get('row')
                if type(row) is not int or row not in source_equipment:
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}].row must be one of the rows shown: {sorted(source_equipment)}"
                    )
                if row in seen_rows:
                    raise CharacterValidationResponseError(
                        f"T051: duplicate equipment update for row {row}"
                    )
                seen_rows.add(row)
                source_item = source_equipment[row]
                reclassified = (
                    row in reclassifiable
                    and 'item_type' in item
                    and item['item_type'] != 'armor'
                )
                for immutable_field in immutable_equipment_fields:
                    if immutable_field == 'item_type' and reclassified:
                        continue
                    if (
                        immutable_field in item
                        and item[immutable_field] != source_item.get(immutable_field)
                    ):
                        raise CharacterValidationResponseError(
                            f"T051: equipment[{index}] may not alter "
                            f"{immutable_field}"
                        )
                # Every proposed armor value is checked against the frozen
                # schema's letter; the model chooses any value inside it.
                contract_errors = armor_contract_errors(
                    [dict(item, item_name=source_item.get('item_name'))], self._equipment_item_schema()
                )
                if contract_errors:
                    raise CharacterValidationResponseError(
                        f"T051: equipment[{index}] violates the character schema: "
                        + "; ".join(contract_errors)
                    )

                normalized_update = {'row': row}
                if reclassified:
                    normalized_update['item_type'] = item['item_type']
                for mutable_field in _T051_ARMOR_FIELDS:
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
Every item you are shown has a row number. Return a JSON object with ONLY the changes needed:
{
  "corrections_made": ["list of corrections"],
  "equipment": [
    {
      "row": 4,
      "item_type": "corrected_type"
    }
  ]
}

CRITICAL: Only return items that need their item_type corrected, each by the row number shown. Do NOT return items that are already correctly categorized. Do NOT return the complete character data - only the rows that need item_type fixes.
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
        
        for item in equipment:
            item_name = item.get('item_name', 'Unknown Item')
            item_type = item.get('item_type', 'Unknown')
            description = item.get('description', 'No description')
            quantity = item.get('quantity', 1)
            
            prompt += f"""
Row {item['row']}:
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

IMPORTANT: Return ONLY the rows that need their item_type corrected, by row number. Do not include items that are already correctly categorized."""
        
        return prompt
    
    def parse_inventory_validation_response(self, ai_response: str, original_data: Dict[str, Any]) -> List[tuple]:
        """
        Check a T052 answer against the rows it was shown.

        Each correction names one offered row by its number and a schema
        item_type that differs from the row's. Returns (row, item_type) pairs.

        Args:
            ai_response: AI response string
            original_data: The offered rows (extract_inventory_data)

        Returns:
            The checked corrections (empty when none are needed)
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
        offered = {item['row']: item for item in original_data.get('equipment', [])}
        retyped = []
        for index, item in enumerate(equipment):
            if not isinstance(item, dict):
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] must be an object"
                )
            unknown_fields = set(item).difference({'row', 'item_type'})
            if unknown_fields:
                raise CharacterValidationResponseError(
                    "T052: equipment update contains unsupported field(s): "
                    + ", ".join(sorted(unknown_fields))
                )
            row = item.get('row')
            if type(row) is not int or row not in offered:
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}].row must be one of the rows shown: {sorted(offered)}"
                )
            if any(done == row for done, _type in retyped):
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] corrects row {row} a second time"
                )
            if not isinstance(item.get('item_type'), str):
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] requires a string item_type"
                )
            normalized_type = item['item_type'].strip().lower()
            if normalized_type not in VALID_INVENTORY_ITEM_TYPES:
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}].item_type is not allowed"
                )
            source_type = str(offered[row].get('item_type', '')).strip().lower()
            if normalized_type == source_type:
                raise CharacterValidationResponseError(
                    f"T052: equipment[{index}] does not change item_type"
                )
            retyped.append((row, normalized_type))

        for correction in corrections:
            debug(f"[Inventory Correction] {correction}", category="character_validation")
            self.logger.info(f"AI Inventory Correction: {correction}")
            self.corrections_made.append(f"Inventory: {correction}")

        if not retyped:
            self.logger.debug("No inventory corrections needed")
        return retyped
    
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
    
    def _apply_consolidation_through_engine(
        self,
        character_data: Dict[str, Any],
        directives: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute checked T054 directives through the engine: each merged or
        duplicate row is removed (core/nql/consolidate), then each merged row's
        typed quantity is added to its ammunition stock (core/nql/ammunition);
        a merge with no stock of that catalog ammunition starts a catalog row.
        A refusal raises the validator's contract error so the loop retries or
        fails open with the sheet unchanged."""
        from core.nql import ammunition as nql_ammunition
        from core.nql import consolidate as nql_consolidate

        removals = [d['item_name'] for d in directives if d['action'] in ('merge', 'duplicate')]
        if not removals:
            return character_data
        outcome = nql_consolidate.transact(character_data, removals, {}, reserved=nql_consolidate.genesis.held_ids_on_disk())
        for gap in outcome.gaps:
            debug(f"[Consolidation Engine] {character_data.get('name')}: {gap}", category="character_validation")
        if not outcome.ok:
            raise CharacterValidationResponseError(
                f"T054: the rules engine refused the removal: {outcome.reason}"
            )
        sheet = outcome.sheet
        for directive in directives:
            entry = directive['entry']
            if directive['action'] == 'duplicate':
                self.corrections_made.append(
                    f"Removed equipment row '{directive['item_name']}' ({directive['quantity']}): "
                    f"the ammunition section already counts these {entry['name']}")
                continue
            if directive['action'] != 'merge':
                continue
            held = nql_ammunition.declared_row_for_catalog(sheet, entry['name'], entry['id'])
            if held is None:
                sheet.setdefault('ammunition', []).append({
                    'name': entry['name'],
                    'quantity': directive['quantity'],
                    'description': directive['description'] if isinstance(directive['description'], str) else entry['name'],
                    'catalog_id': entry['id'],
                })
                self.corrections_made.append(
                    f"Moved '{directive['item_name']}' ({directive['quantity']}) to a new {entry['name']} ammunition row")
                continue
            row = held[1]
            before = row['quantity']
            added = nql_ammunition.add(sheet, row['name'], directive['quantity'])
            if not added.ok:
                raise CharacterValidationResponseError(
                    f"T054: the rules engine refused adding {directive['quantity']} to {row['name']!r}: {added.reason}"
                )
            nql_ammunition.write_back(row, added)
            self.corrections_made.append(
                f"Moved '{directive['item_name']}' ({directive['quantity']}) into {row['name']}: "
                f"{before} -> {row['quantity']} [engine]")
        return sheet

    def ai_consolidate_inventory_with_result(
        self,
        character_data: Dict[str, Any],
    ) -> CharacterValidationResult:
        """
        T054: the model decides, for each equipment row typed as ammunition,
        whether it is extra stock (merge), stock the ammunition section already
        counts (duplicate) or an item to keep. Code checks the answer against the
        typed rows and the engine executes it; amounts are the rows' typed
        quantities. Coins are never consolidated here: they reach the purse
        through the typed currency change.

        Args:
            character_data: Character JSON data
            
        Returns:
            Character data with the decided rows moved through the engine (from cache if unchanged)
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
        strict = self.provider_scope is not None and self.provider_scope.completion_required
        last_candidate = None
        
        max_attempts = 3
        attempt = 1
        corrections_before = copy.deepcopy(self.corrections_made)
        
        while strict or attempt <= max_attempts:
            ai_response = None
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

                messages = [
                    {"role": "system", "content": self.get_inventory_consolidation_system_prompt()},
                    {"role": "user", "content": consolidation_prompt}
                ]
                if last_candidate is not None:
                    raw, objection = last_candidate
                    messages.extend([
                        {"role": "assistant", "content": raw if isinstance(raw, str) else ""},
                        {"role": "user", "content": (
                            "Your last response failed this validator's contract: " + objection
                            + ". Return the complete JSON object required by the unchanged system "
                              "and user instructions. Correct the stated defect and preserve valid fields.")},
                    ])
                response = capture_and_fanout("T054", api_client.create_completion,
                    _detached_scope=self.provider_scope,
                    _detached_status=self.provider_status,
                    _live_selected='advisory' if self.provider_scope is not None else None,
                    _request_provider=MODEL_PROVIDER,
                    messages=messages,
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
                
                ai_response = response.choices[0].message.content
                if not strict:
                    ai_response = ai_response.strip()
                
                directives = self.parse_ammunition_consolidation_response(
                    ai_response,
                    consolidation_data,
                    character_data,
                )
                # The engine removes the merged and duplicate rows and adds
                # each merged row's typed quantity to its stock.
                corrected_data = self._apply_consolidation_through_engine(character_data, directives)

                # Cache only a successfully merged final state. A failed later
                # file write leaves a different source hash and therefore cannot
                # suppress a healing retry.
                final_currency_hash = self._compute_currency_hash(
                    self.extract_currency_consolidation_data(corrected_data)
                )
                self._update_currency_cache(character_name, final_currency_hash)
                return _validation_result(character_data, corrected_data)
                    
            except Exception as e:
                if self.commit_guard is not None and isinstance(e, LiveProviderSuperseded):
                    raise
                self.corrections_made = copy.deepcopy(corrections_before)
                if strict:
                    if isinstance(e, LiveProviderUnavailable) and e.envelope.get('disposition') == 'empty':
                        continue
                    if isinstance(e, CharacterValidationResponseError):
                        last_candidate = (ai_response, str(e))
                        continue
                    raise
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
        """System prompt for T054: one decision per equipment row typed as ammunition."""
        return """You keep a character's ammunition in one place for the 5th edition of the world's most popular role playing game.

The character sheet has an AMMUNITION SECTION: the stocks that attacks spend. Some EQUIPMENT ROWS are typed as ammunition too. For every equipment row you are shown, decide what it is:
- "merge": ammunition the character carries IN ADDITION to the ammunition section, for example a bundle found or bought and written into equipment. The row is removed and its quantity is added to the stock of the catalog ammunition you name.
- "duplicate": the same ammunition the ammunition section already counts, for example starting gear written into both places, often with an older count. The row is removed and the ammunition section stays as it is.
- "keep": anything that must stay an item: magical or special ammunition (+1, silvered, adamantine, elemental), a sealed or unopened bundle, or a row you are unsure about.

When the ammunition section already holds a stock of the same ammunition and nothing shows the character gained more, the row is a "duplicate". Never "merge" a row unless the sheet shows it is carried in addition to the ammunition section. When unsure, answer "keep".

Name the ammunition with exactly one of the catalog names you are given. Do not state counts: the row's quantity is the amount.

Return only this JSON object, with one entry for every row you are shown:
{
  "rows": [
    {"row": 7, "action": "duplicate", "ammunition": "Arrows"},
    {"row": 9, "action": "merge", "ammunition": "Bolts"},
    {"row": 12, "action": "keep"}
  ]
}
- "row" is the row number shown.
- "ammunition" is required for merge and duplicate, and left out for keep."""
    
    def build_inventory_consolidation_prompt(self, consolidation_data: Dict[str, Any]) -> str:
        """The T054 user prompt: the ammunition section, the catalog names and the offered rows."""
        lines = [f"CHARACTER NAME: {consolidation_data.get('name', 'Unknown')}", "", "AMMUNITION SECTION (the stocks attacks spend):"]
        stocks = [row for row in consolidation_data.get('ammunition') or [] if isinstance(row, dict)]
        for row in stocks:
            entry = item_catalog.ammunition_entry(row)
            catalog = f" (catalog: {entry['name']})" if entry else ""
            lines.append(f"- {row.get('name', 'Unknown')}: {row.get('quantity', 0)}{catalog}")
        if not stocks:
            lines.append("- None")
        lines += ["", "CATALOG AMMUNITION NAMES: " + ", ".join(sorted(e['name'] for e in _catalog_ammunition().values())),
                  "", "EQUIPMENT ROWS TYPED AS AMMUNITION:"]
        for candidate in consolidation_data.get('equipment', []):
            item = candidate['item']
            lines += ["", f"Row {candidate['row']}:",
                      f"- Name: {item.get('item_name')}",
                      f"- Type: {item.get('item_type', 'Unknown')}",
                      f"- Quantity: {item.get('quantity')}",
                      f"- Description: {item.get('description', 'No description')}"]
            own = _row_catalog_ammunition(item)
            if own is not None:
                lines.append(f"- Catalog ammunition: {own.get('name')}")
        lines += ["", "Answer merge, duplicate or keep for every row."]
        return "\n".join(lines)

    def parse_ammunition_consolidation_response(
        self,
        ai_response: str,
        consolidation_data: Dict[str, Any],
        character_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Check a T054 answer against the typed rows it was shown.

        Every offered row is answered exactly once with merge, duplicate or
        keep. Merge and duplicate name a catalog ammunition entry (the row's own
        when its catalog id or exact name is one). A duplicate needs a stock of that ammunition
        on the sheet; a merge allows at most one, which receives the row's typed
        quantity. Returns the directives with each row's name and quantity."""
        from core.nql import genesis

        parsed = _load_response_object(ai_response, "T054")
        unknown = set(parsed).difference({'rows'})
        if unknown:
            raise CharacterValidationResponseError(
                "T054: response contains unsupported field(s): " + ", ".join(sorted(unknown))
            )
        answers = parsed.get('rows')
        if not isinstance(answers, list):
            raise CharacterValidationResponseError("T054: 'rows' must be an array")
        offered = {candidate['row']: candidate['item'] for candidate in consolidation_data.get('equipment', [])}
        catalog = _catalog_ammunition()
        stocks = [row for _stock, row in genesis.ammunition_rows(character_data, [])]
        directives = []
        for index, answer in enumerate(answers):
            path = f"T054: rows[{index}]"
            if not isinstance(answer, dict) or set(answer).difference({'row', 'action', 'ammunition'}):
                raise CharacterValidationResponseError(f"{path} must be an object with only row, action and ammunition")
            row = answer.get('row')
            if type(row) is not int or row not in offered:
                raise CharacterValidationResponseError(f"{path}.row must be one of the rows shown: {sorted(offered)}")
            if any(directive['row'] == row for directive in directives):
                raise CharacterValidationResponseError(f"{path} answers row {row} a second time")
            action = answer.get('action')
            if action not in ('merge', 'duplicate', 'keep'):
                raise CharacterValidationResponseError(f"{path}.action must be merge, duplicate or keep")
            item = offered[row]
            directive = {'row': row, 'action': action, 'item_name': item['item_name'],
                         'quantity': item['quantity'], 'description': item.get('description'), 'entry': None}
            if action == 'keep':
                if 'ammunition' in answer:
                    raise CharacterValidationResponseError(f"{path}: keep takes no ammunition")
                directives.append(directive)
                continue
            name = answer.get('ammunition')
            entry = catalog.get(name.strip().casefold()) if isinstance(name, str) else None
            if entry is None:
                raise CharacterValidationResponseError(
                    f"{path}.ammunition must be one of {sorted(e['name'] for e in catalog.values())}"
                )
            own = _row_catalog_ammunition(item)
            if own is not None and own.get('id') != entry.get('id'):
                raise CharacterValidationResponseError(
                    f"{path}: row {row} is catalog {own.get('name')!r}, not {entry['name']!r}"
                )
            held = [stock for stock in stocks if (item_catalog.ammunition_entry(stock) or {}).get('id') == entry.get('id')]
            if action == 'duplicate' and not held:
                raise CharacterValidationResponseError(
                    f"{path}: the ammunition section holds no {entry['name']} stock, so row {row} "
                    "is not a duplicate; answer merge or keep"
                )
            if action == 'merge' and len(held) > 1:
                raise CharacterValidationResponseError(
                    f"{path}: {len(held)} ammunition rows hold {entry['name']}; answer duplicate or keep"
                )
            directive['entry'] = entry
            directives.append(directive)
        missing = sorted(set(offered).difference(directive['row'] for directive in directives))
        if missing:
            raise CharacterValidationResponseError(f"T054: rows {missing} were not answered")
        return directives

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
