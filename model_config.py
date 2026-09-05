# Model Configuration Settings
# This file contains all AI model configurations and can be safely committed to git
import copy
import json
import os

from model_registry import CALLSITE_BINDINGS, SUPPORTED_PROVIDERS
from utils.secret_store import delete_secret, get_secret, set_secret


def convert_to_gemini_schema(
    json_schema,
    preserve_required=False,
    preserve_constraints=False,
):
    """Convert JSON Schema Draft-07 to Gemini API response_schema format.

    Strips $schema, normally strips required, takes the first oneOf option,
    and uppercases types. ``preserve_required`` is reserved for contracts such
    as T040 that require a complete verdict; character-delta schemas must stay
    partial and therefore keep the historical default. ``preserve_constraints``
    copies the JSON-Schema constraints supported by Gemini's response-schema
    surface. Both options default off so existing callsites retain their
    historical schema shape.
    Handles union types like ["integer", "null"] by taking the non-null type.
    Reusable for any callsite that needs Gemini response_schema forcing.
    """
    _TYPE_MAP = {
        "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
        "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
    }
    _SUPPORTED_CONSTRAINTS = (
        "enum",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        "minProperties",
        "maxProperties",
        "pattern",
        "description",
        "format",
    )

    def _copy_constraints(source, target):
        if not preserve_constraints:
            return
        for key in _SUPPORTED_CONSTRAINTS:
            if key in source:
                target[key] = copy.deepcopy(source[key])

    def _convert_prop(prop):
        result = {}
        prop_type = prop.get("type")
        if isinstance(prop_type, list):
            non_null = [t for t in prop_type if t != "null"]
            prop_type = non_null[0] if non_null else "string"
        if prop_type:
            result["type"] = _TYPE_MAP.get(prop_type, "STRING")
        if "oneOf" in prop and "type" not in result:
            first = prop["oneOf"][0]
            if preserve_constraints:
                # The historical converter intentionally takes the first oneOf
                # branch. In strict-contract mode, recursively keep that
                # branch's supported nested constraints as well.
                result.update(_convert_prop(first))
            elif "type" in first:
                result["type"] = _TYPE_MAP.get(first["type"], "STRING")
            if not preserve_constraints and "items" in first:
                result["type"] = "ARRAY"
                result["items"] = _convert_prop(first["items"])
        if "properties" in prop:
            result["type"] = "OBJECT"
            result["properties"] = {
                k: _convert_prop(v) for k, v in prop["properties"].items()
            }
        if "items" in prop:
            result["type"] = "ARRAY"
            result["items"] = _convert_prop(prop["items"])
        if preserve_required and isinstance(prop.get("required"), list):
            result["required"] = list(prop["required"])
        # Do not copy Draft-07 metadata such as $schema or examples, or
        # provider-specific additionalProperties.
        _copy_constraints(prop, result)
        return result

    result = {
        "type": "OBJECT",
        "properties": {
            k: _convert_prop(v)
            for k, v in json_schema.get("properties", {}).items()
        },
    }
    if preserve_required and isinstance(json_schema.get("required"), list):
        result["required"] = list(json_schema["required"])
    _copy_constraints(json_schema, result)
    return result


# Load and convert char_schema.json for Gemini response_schema
_char_schema_path = os.path.join(os.path.dirname(__file__), "schemas", "char_schema.json")
if os.path.exists(_char_schema_path):
    with open(_char_schema_path, "r") as _f:
        _CHAR_SCHEMA_GEMINI = convert_to_gemini_schema(json.load(_f))
else:
    _CHAR_SCHEMA_GEMINI = None
    import logging as _logging
    _logging.warning(
        "schemas/char_schema.json not found -- Gemini response_schema "
        "forcing disabled. Gemini may output narration instead of deltas."
    )

# Load and convert storage_action_schema.json for Gemini response_schema (T049).
# Without it, gemini-flash-lite emits narration instead of a storage operation and
# the action silently fails. Same load-and-convert pattern as char_schema above.
_storage_schema_path = os.path.join(os.path.dirname(__file__), "schemas", "storage_action_schema.json")
if os.path.exists(_storage_schema_path):
    with open(_storage_schema_path, "r") as _f:
        _STORAGE_ACTION_SCHEMA_GEMINI = convert_to_gemini_schema(json.load(_f))
else:
    _STORAGE_ACTION_SCHEMA_GEMINI = None


# --- Main Game Logic Models (used in main.py) ---
DM_MAIN_MODEL = "gpt-4.1-2025-04-14"
DM_SUMMARIZATION_MODEL = "gpt-4.1-mini-2025-04-14"
DM_VALIDATION_MODEL = "gpt-4.1-2025-04-14"

# --- Action Prediction Model (used in action_predictor.py) ---
ACTION_PREDICTION_MODEL = "gpt-4.1-2025-04-14"  # Use full model for accurate action prediction

# --- Combat Simulation Models (used in combat_manager.py) ---
COMBAT_MAIN_MODEL = "gpt-4.1-2025-04-14"
# COMBAT_SCHEMA_UPDATER_MODEL - This was defined but not directly used.
# If needed for update_player_info, update_npc_info, update_encounter called from combat_sim,
# those modules will use their own specific models defined below.
COMBAT_DIALOGUE_SUMMARY_MODEL = "gpt-4.1-mini-2025-04-14"

# --- Utility and Builder Models ---
NPC_BUILDER_MODEL = "gpt-4.1-2025-04-14"                # Used in npc_builder.py
ADVENTURE_SUMMARY_MODEL = "gpt-4.1-mini-2025-04-14"
CHARACTER_VALIDATOR_MODEL = "gpt-4.1-2025-04-14"    # Used in adv_summary.py
PLOT_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"          # Used in plot_update.py
PLAYER_INFO_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"   # Used in update_player_info.py
NPC_INFO_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"      # Used in update_npc_info.py
MONSTER_BUILDER_MODEL = "gpt-4.1-2025-04-14"
ENCOUNTER_UPDATE_MODEL = "gpt-4.1-mini-2025-04-14"
LEVEL_UP_MODEL = "gpt-4.1-2025-04-14"                  # Used in level_up.py
DM_EFFECTS_MODEL = "gpt-4.1-2025-04-14"               # Used in update_character_effects.py

# --- Transition Validation Model ---
TRANSITION_VALIDATOR_MODEL = "gpt-4.1-mini-2025-04-14"  # Used in transition_validator.py
TRANSITION_VALIDATOR_TEMPERATURE = 0.3                   # Low temp for analytical reasoning

# --- Token Optimization Models ---
DM_MINI_MODEL = "gpt-4.1-mini-2025-04-14"              # Used for simple conversations and plot-only updates
DM_FULL_MODEL = "gpt-4.1-2025-04-14"                   # Used for complex actions requiring JSON operations

# --- T067 Main DM Loop Model Configs (from capture testing) ---
# Each dict bundles model string + provider-specific params.
# Temperature is NOT included -- it stays at the callsite.

# OpenAI
DM_FULL_MODEL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
DM_MINI_MODEL_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3.1 models - conservative params until capture data collected)
DM_FULL_MODEL_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
DM_MINI_MODEL_GEMINI_FLASH_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low"}

# Legacy (no extra params)
DM_FULL_MODEL_LEGACY = {"model": "gpt-4.1-2025-04-14"}
DM_MINI_MODEL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}

# LM Studio (local passthrough - no extra params, routes through OpenAI client to localhost)
DM_FULL_MODEL_LMSTUDIO = {"model": "local-model"}
DM_MINI_MODEL_LMSTUDIO = {"model": "local-model"}

# --- T065 AI Response Validation Model Configs (from capture + manual testing) ---
# Validation requires reasoning -- gpt-5.2|none is UNUSABLE (0/15 correct).
# Temperature is 0.1 at callsite (stays there, not in config).

# OpenAI (reasoning=low required for validation accuracy)
DM_VALIDATION_GPT52_LOW = {"model": "gpt-5.2", "reasoning_effort": "low"}

# Gemini (3-flash with low thinking -- live replay: 2/2 correct)
DM_VALIDATION_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# Legacy (no extra params)
DM_VALIDATION_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
DM_VALIDATION_LMSTUDIO = {"model": "local-model"}

# --- T082 Action Predictor Model Configs (from capture testing) ---
# Binary classifier, fires every turn. Speed and cost critical.
# Temperature is 0.1 at callsite.

# OpenAI (mini model with low reasoning -- 14/14 correct, $0.0007, 2.8s)
ACTION_PRED_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3-flash with low thinking -- 13/14 correct, $0.0011, 1.4s fastest)
ACTION_PRED_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# Legacy (full model, no extra params -- matches current ACTION_PREDICTION_MODEL)
ACTION_PRED_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
ACTION_PRED_LMSTUDIO = {"model": "local-model"}

# --- T079 Character Update Model Configs (from capture + simulation testing) ---
# Gemini requires response_schema to prevent narration output. Schema is
# auto-converted from schemas/char_schema.json at runtime -- no separate file.
# Existing purge_invalid_fields() strips spurious extra keys from output.
# Temperature is 0.7 at callsite.

# OpenAI (mini model with low reasoning)
CHAR_UPDATE_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3.1 flash-lite with low thinking + request-scoped schema)
CHAR_UPDATE_GEMINI_FLASHLITE_LOW = {
    "model": "gemini-3.1-flash-lite-preview",
    "thinking_level": "low",
    "response_schema": _CHAR_SCHEMA_GEMINI,
}

# Legacy (no extra params -- matches current PLAYER_INFO_UPDATE_MODEL)
CHAR_UPDATE_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}

# LM Studio (local passthrough)
CHAR_UPDATE_LMSTUDIO = {"model": "local-model"}

# --- T017 Combat Compression Model Configs (from synthetic testing v5 prompt) ---
# CRITICAL: This callsite outputs plain text tags (@T=CS/v2), NOT JSON.
# response_format=None opts out of default JSON mode.
# Temperature is 0.3 at callsite.

# OpenAI (mini model with low reasoning -- 5/6 correct, entry 4 @ROUND cosmetic only)
COMBAT_COMPRESS_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low", "response_format": None}

# Gemini (3-flash with low thinking -- stable 6/6, 2.0s avg, fastest)
COMBAT_COMPRESS_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low", "response_format": None}

# Legacy (no extra params)
COMBAT_COMPRESS_LEGACY = {"model": "gpt-4.1-mini-2025-04-14", "response_format": None}

# LM Studio (local passthrough)
COMBAT_COMPRESS_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T096/T097 Agentic Combat -----
# T096 selects one ordered tactical intent per persisted actor window. T097
# narrates already-committed events. Both avoid reasoning-heavy variants: code
# owns arithmetic, ordering, validation, and recovery.
_AGENTIC_COMBAT_INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "stateVersion": {"type": "integer"},
        "intents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "actorId": {"type": "string"},
                    "mode": {"type": "string", "enum": ["known", "adjudicated"]},
                    "action": {"type": "string"},
                    "ability": {"type": "string"},
                    "targetId": {"type": "string"},
                    "description": {"type": "string"},
                    "save": {"type": "object"},
                    "targets": {"type": "array", "items": {"type": "object"}},
                    "resources": {"type": "array", "items": {"type": "object"}},
                    "effects": {"type": "array", "items": {"type": "object"}},
                    "requiresPlayerInput": {"type": "object"},
                },
                "required": ["actorId", "mode"],
            },
        },
    },
    "required": ["stateVersion", "intents"],
}
_AGENTIC_COMBAT_NARRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "narration": {"type": "string"},
        "coveredEventIds": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["narration", "coveredEventIds"],
}
COMBAT_INTENT_GPT54_NONE = {"model": "gpt-5.4", "reasoning_effort": "none"}
COMBAT_INTENT_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(
        _AGENTIC_COMBAT_INTENT_SCHEMA,
        preserve_required=True,
        preserve_constraints=True,
    ),
}
COMBAT_INTENT_LEGACY = {"model": "gpt-4.1-2025-04-14"}
COMBAT_INTENT_LMSTUDIO = {"model": "local-model"}
COMBAT_NARRATE_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
COMBAT_NARRATE_GPT54MINI_LOW = {"model": "gpt-5.4-mini", "reasoning_effort": "low"}
COMBAT_NARRATE_GPT54MINI_MEDIUM = {"model": "gpt-5.4-mini", "reasoning_effort": "medium"}
COMBAT_NARRATE_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(
        _AGENTIC_COMBAT_NARRATION_SCHEMA,
        preserve_required=True,
        preserve_constraints=True,
    ),
}
COMBAT_NARRATE_GEMINI_FLASH_MEDIUM = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "medium",
    "response_schema": convert_to_gemini_schema(
        _AGENTIC_COMBAT_NARRATION_SCHEMA,
        preserve_required=True,
        preserve_constraints=True,
    ),
}
COMBAT_NARRATE_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
COMBAT_NARRATE_LMSTUDIO = {"model": "local-model"}

# ----- T046 Initiative Tracker -----
# Analytical combat utility: tracks turn order, determines who acts next.
# Full-tier callsite, temperature=0.1, plain text output.
# GPT-5.4 reviewer: gpt-5.2|none = 4/4 pass (4.2/5), gemini-flash|low = 4/4 pass (4.2/5)
# gpt-5-mini DISQUALIFIED (contradictory tracker on E[1], scored 1-2/5)
# MED-12 (#127): deliberately stays on gpt-5.2 (not gpt-5.4 like T040/T042/T043).
# Capture data: gpt-5.2|none scored 4/4 here; no measured benefit from gpt-5.4 for
# this analytical turn-order task. Do not "upgrade" to 5.4 without re-running capture.

# OpenAI (gpt-5.2 with no reasoning -- 4/4 correct, 2.46s avg, temp=0.1 passes through)
INIT_TRACKER_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none", "response_format": None}

# Gemini (3-flash with low thinking -- 4/4 correct, 1.71s avg, fastest + cheapest)
INIT_TRACKER_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low", "response_format": None}

# Legacy (no extra params -- response_format=None opts out of default JSON mode)
INIT_TRACKER_LEGACY = {"model": "gpt-4.1-2025-04-14", "response_format": None}

# LM Studio (local passthrough)
INIT_TRACKER_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T078 Character Effects -----
# Analyzes character updates for trackable temporary effects (buffs/debuffs).
# Full-tier callsite, temperature=0.3, JSON output.
# GPT-5.4 reviewer: gpt-5.2|none = 5/5 pass (4.4/5), gemini-flash|high = 5/5 pass (4.4/5)
# gemini-flash|low scored 3/5 on Sneak Attack entry (contradictory duration metadata)

# OpenAI (gpt-5.2 with no reasoning -- 5/5 pass, 4.4/5 avg, 1.31s, temp=0.3 passes through)
CHAR_EFFECTS_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with high thinking -- 5/5 pass, 4.4/5 avg, 2.89s, cheapest at $0.0006/call)
CHAR_EFFECTS_GEMINI_FLASH_HIGH = {"model": "gemini-3-flash-preview", "thinking_level": "high"}

# Legacy (no extra params)
CHAR_EFFECTS_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
CHAR_EFFECTS_LMSTUDIO = {"model": "local-model"}

# ----- T040 Combat Validation -----
# Validates AI combat responses for D&D rules compliance.
# Full-tier callsite, temperature=0.3, JSON output.
# GPT-5.4 reviewer: gpt-5.4|none = 4/4 pass (4.50/5), gemini-flash|low = 4/4 pass (4.0/5)
# gpt-5.2 FAILS validation (over-rejects valid responses at all reasoning levels)
# REQUIRES v4 prompt changes to combat_validation_prompt_compressed.txt

# OpenAI (gpt-5.4 with no reasoning -- retained as fallback reference)
COMBAT_VALID_GPT54_NONE = {"model": "gpt-5.4", "reasoning_effort": "none"}

# OpenAI selected (gpt-5.6-terra, low reasoning). Replaces gpt-5.4 as the T040
# combat referee after adversarial + broad testing:
#  - Poisoned player-pause case (DM plan hallucinates a 3-actor window while the
#    authoritative state window is player-only): gpt-5.4 AND luna|low false-positive
#    rejected legitimate play (jamming combat in a retry loop); terra|low was correct.
#  - 45-case randomized battery across 15 rule dimensions: terra|low caught 33/33
#    violation types (0 false negatives) and passed all valid cases (0 false
#    positives once valid candidates echo the turn window, per plan_must_echo).
# Chosen over sol|none on cost: identical correctness at ~2.3x lower price
# (terra $2/$12 vs sol $5/$30 per 1M in/out). terra|medium/high add no accuracy.
# gpt-5.6-sol / gpt-5.4 profiles retained above as references.
COMBAT_VALID_TERRA_LOW = {"model": "gpt-5.6-terra", "reasoning_effort": "low"}
COMBAT_VALID_SOL_NONE = {"model": "gpt-5.6-sol", "reasoning_effort": "none"}

# Gemini (3-flash with low thinking -- 4/4 correct, 1.6s avg, cheapest)
# MED-1 (#127): inline schema for T040 combat validation (no schema file exists).
# Shape mirrors what combat_manager.py reads: validation_json.get("valid") and
# feedback_obj.get("positive"/"negative"/"recommendation"). Converted for Gemini
# so flash returns this structure instead of mis-shaped JSON (avoids 5 retries).
_T040_COMBAT_VALIDATION_SCHEMA = {
    "type": "object",
    "required": ["valid", "feedback"],
    "properties": {
        "valid": {"type": "boolean"},
        "feedback": {
            "type": "object",
            "required": ["positive", "negative", "recommendation"],
            "properties": {
                "positive": {"type": "string"},
                "negative": {"type": "string"},
                "recommendation": {"type": "string"},
            },
        },
    },
}
COMBAT_VALID_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(
        _T040_COMBAT_VALIDATION_SCHEMA,
        preserve_required=True,
    ),
}

# Legacy (no extra params)
COMBAT_VALID_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
COMBAT_VALID_LMSTUDIO = {"model": "local-model"}

# ----- T051 Character Validator -----
# Validates character AC calculations per 5e rules.
# Full-tier callsite, temperature=0.1, JSON output.
# GPT-5.4 reviewer: gpt-5.2|none = 3/3 pass (4.0/5), gemini-flash|low = 3/3 pass (4.3/5)
# Easy callsite -- all next-gen models pass. gpt-5.4-mini DISQUALIFIED (miscalculated Dex modifier)

# OpenAI (gpt-5.2 with no reasoning -- 3/3 correct, 6.0s avg, temp=0.1 passes through)
CHAR_VALIDATOR_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with low thinking -- 3/3 correct, 4.0s avg, fastest + cheapest)
# T051, T052, and T053 have different parsers and therefore need different
# structured-output contracts. Sharing T053's combined shape with the two
# single-purpose validators produces valid JSON that their parsers ignore.
_T051_AC_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "validated_character_data": {
            "type": "object",
            "properties": {
                "armorClass": {"type": "integer"},
                "equipment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_name": {"type": "string"},
                            "item_type": {"type": "string"},
                            "equipped": {"type": "boolean"},
                            "ac_base": {"type": "number"},
                            "ac_bonus": {"type": "number"},
                            "dex_limit": {"type": "number"},
                            "armor_category": {"type": "string"},
                            "stealth_disadvantage": {"type": "boolean"},
                        },
                    },
                },
            },
        },
        "corrections_made": {"type": "array", "items": {"type": "string"}},
        "ac_calculation_breakdown": {
            "type": "object",
            "properties": {
                "base_armor": {"type": "string"},
                "dex_modifier": {"type": "string"},
                "shield_bonus": {"type": "string"},
                "fighting_style_bonus": {"type": "string"},
                "total_ac": {"type": "integer"},
            },
        },
    },
}

_T052_INVENTORY_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "corrections_made": {"type": "array", "items": {"type": "string"}},
        "equipment": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string"},
                    "item_type": {"type": "string"},
                },
            },
        },
    },
}

_T053_COMBINED_VALIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "ac_validation": {
            "type": "object",
            "properties": {
                "current_ac": {"type": "integer"},
                "calculated_ac": {"type": "integer"},
                "correction_needed": {"type": "boolean"},
                "breakdown": {"type": "string"},
                "corrections": {"type": "array", "items": {"type": "string"}},
            },
        },
        "inventory_corrections": {
            "type": "object",
            "properties": {
                "corrections_made": {"type": "array", "items": {"type": "string"}},
                "equipment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_name": {"type": "string"},
                            "item_type": {"type": "string"},
                        },
                    },
                },
            },
        },
        "currency_consolidation": {
            "type": "object",
            "properties": {
                "corrections_made": {"type": "array", "items": {"type": "string"}},
                "currency": {
                    "type": "object",
                    "properties": {
                        "platinum": {"type": "integer"},
                        "gold": {"type": "integer"},
                        "electrum": {"type": "integer"},
                        "silver": {"type": "integer"},
                        "copper": {"type": "integer"},
                    },
                },
                "items_to_remove": {"type": "array", "items": {"type": "string"}},
                "ammunition": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                    },
                },
                "ammo_items_to_remove": {"type": "array", "items": {"type": "string"}},
            },
        },
        "class_feature_validation": {
            "type": "object",
            "properties": {
                "duplicates_found": {"type": "array", "items": {"type": "string"}},
                "corrections_made": {"type": "array", "items": {"type": "string"}},
                "features_to_remove": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

_T054_CURRENCY_CONSOLIDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "currency": {
            "type": "object",
            "properties": {
                "platinum": {"type": "integer"},
                "gold": {"type": "integer"},
                "electrum": {"type": "integer"},
                "silver": {"type": "integer"},
                "copper": {"type": "integer"},
            },
        },
        "ammunition": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "integer"},
                },
            },
        },
        "equipment": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string"},
                    "new_item_name": {"type": "string"},
                    "_remove": {"type": "boolean"},
                    "_update": {"type": "boolean"},
                },
            },
        },
        "consolidations_made": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}
CHAR_VALIDATOR_T051_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(_T051_AC_VALIDATION_SCHEMA),
}
CHAR_VALIDATOR_T052_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(_T052_INVENTORY_VALIDATION_SCHEMA),
}
CHAR_VALIDATOR_T053_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(_T053_COMBINED_VALIDATION_SCHEMA),
}
CHAR_VALIDATOR_T054_GEMINI_FLASH_LOW = {
    "model": "gemini-3-flash-preview",
    "thinking_level": "low",
    "response_schema": convert_to_gemini_schema(
        _T054_CURRENCY_CONSOLIDATION_SCHEMA
    ),
}

# Legacy (no extra params)
CHAR_VALIDATOR_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
CHAR_VALIDATOR_LMSTUDIO = {"model": "local-model"}

# ----- T050 Effects Gemini Config -----
# T054 has a dedicated schema-bearing config above.
CHAR_VALIDATOR_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# ----- T034 Monster Builder -----
# Creates monster stat blocks from name + party level.
# Full-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: gemini-flash|low = 3/3 pass (4.3/5), gpt-5.2|none = 3/3 pass (3.7/5)

# OpenAI (gpt-5.2 with no reasoning -- 3/3 correct, 5.1s avg, temp=0.7 passes through)
MONSTER_BUILD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with low thinking -- 3/3 correct, 2.7s avg, highest quality + cheapest)
MONSTER_BUILD_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# Legacy (no extra params)
MONSTER_BUILD_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
MONSTER_BUILD_LMSTUDIO = {"model": "local-model"}

# ----- T035 NPC Builder -----
# Creates full NPC character sheets from name + race/class/level.
# Full-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: gpt-5.2|none = 3/3 pass (4.0/5), gemini-flash|low = 3/3 pass (4.0/5)
# REQUIRES v4 prompt changes in npc_builder.py (name handling, equipment, racial traits)

# OpenAI (gpt-5.2 with no reasoning -- 3/3 correct, 34s avg, temp=0.7 passes through)
NPC_BUILD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with low thinking -- 3/3 correct, 10s avg, 3x faster + cheaper)
NPC_BUILD_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# Legacy (no extra params)
NPC_BUILD_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
NPC_BUILD_LMSTUDIO = {"model": "local-model"}

# ----- T081 Encounter Update -----
# Updates encounter creature data after combat actions.
# Mini-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: all models 3/3 pass. gemini-flash|low = 5.0/5 avg.
# T081: inline Gemini response_schema (no schema file fits a creatures-delta).
# Without it, gemini-flash drifts to narration and the encounter update silently
# no-ops. Covers only the fields update_encounter parses from each creature.
_T081_ENCOUNTER_UPDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "creatures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "currentHitPoints": {"type": "integer"},
                    "maxHitPoints": {"type": "integer"},
                    "status": {"type": "string"},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}
ENCOUNTER_UPD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
ENCOUNTER_UPD_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low", "response_schema": convert_to_gemini_schema(_T081_ENCOUNTER_UPDATE_SCHEMA)}
ENCOUNTER_UPD_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
ENCOUNTER_UPD_LMSTUDIO = {"model": "local-model"}

# ----- T077 Plot Update -----
# Updates plot progression after game events.
# Mini-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: all models 2/2 pass. gpt-5.2|none = 5.0/5 avg.
PLOT_UPD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
PLOT_UPD_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
PLOT_UPD_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
PLOT_UPD_LMSTUDIO = {"model": "local-model"}

# ----- T021 Transition Validation -----
# Validates location transitions (path blocking, encounter checks).
# Mini-tier callsite, temperature from TRANSITION_VALIDATOR_TEMPERATURE (0.3), JSON output.
# GPT-5.4 reviewer: all models 2/2 pass. gpt-5.2|none = 5.0/5 avg.
TRANSITION_VAL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
TRANSITION_VAL_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
TRANSITION_VAL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
TRANSITION_VAL_LMSTUDIO = {"model": "local-model"}

# ----- T048 Level Up Validation -----
# Validates AI-generated level-up actions against 5e rules.
# Full-tier callsite, temperature=0.2, JSON output.
# 8/8 perfect on expanded synthetic tests (v4 prompt + leveling_info.txt).
# Uses gemini-3-PRO (not flash -- flash missed Barbarian wrong-die edge case)
LEVELUP_VAL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
LEVELUP_VAL_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
LEVELUP_VAL_LEGACY = {"model": "gpt-4.1-2025-04-14"}
LEVELUP_VAL_LMSTUDIO = {"model": "local-model"}

# --- T047: Level-Up Conversation (interactive interview, temp=0.7) ---
# v3 prompt tested: 100% pass rate across 24 synthetic tests (8 scenarios x 3 models).
# gpt-5.2|none: 3.6s avg, best narrative. gemini-flash|low: 1.9s avg, best HP math.
# gpt-5-mini DISQUALIFIED (no temperature support, interview needs temp=0.7).
LEVELUP_CONV_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
LEVELUP_CONV_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
LEVELUP_CONV_LEGACY = {"model": "gpt-4.1-2025-04-14"}
LEVELUP_CONV_LMSTUDIO = {"model": "local-model"}

# --- T086: NPC Auto-Level-Up (single-shot JSON, temp=0.3) ---
# Same model selections as T047 -- simpler task, all models pass easily.
# Uses same LEVELUP_CONV configs (no separate dicts needed -- same models work).

# --- T014/T091: NPC Info Updates (movement decisions + monster reconciliation) ---
# 40/40 synthetic tests passed. Mini-tier callsite (NPC_INFO_UPDATE_MODEL).
# T014: NPC movement decision, temp=0.7, JSON object output.
# T091: Monster reconciliation, temp=0.2, JSON ARRAY output (response_format=None).
NPC_INFO_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
NPC_INFO_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
NPC_INFO_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}

# T014 (NPC movement decision) needs its OWN Gemini config with response_schema.
# It must NOT reuse NPC_INFO_GEMINI_FLASH_LOW above: that config is shared with
# T091 (utils/reconcile_location_state.py), which outputs a top-level JSON ARRAY --
# attaching this object schema there would corrupt T091's monster reconciliation.
_T014_NPC_MOVEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string"},
        "reasoning": {"type": "string"},
        "newDescription": {"type": "string"},
        "newAttitude": {"type": "string"},
        "newLocation": {"type": "string"},
        "locationUpdate": {"type": "string"},
    },
}
NPC_MOVEMENT_T014_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low", "response_schema": convert_to_gemini_schema(_T014_NPC_MOVEMENT_SCHEMA)}
NPC_INFO_LMSTUDIO = {"model": "local-model"}

# T091 uses response_format=None at the callsite (JSON array output, not object).
# T014 uses default JSON mode (JSON object output).

# --- T041: Combat Dialogue Summary (narrative summary of combat encounters) ---
# 10/10 on v2 prompt (5 scenarios x 2 models). Mini-tier (COMBAT_DIALOGUE_SUMMARY_MODEL).
# Creative writing, temp=0.8. PLAIN TEXT output (response_format=None).
# gpt-5-mini DISQUALIFIED (no temperature support at 0.8).
COMBAT_SUMMARY_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
COMBAT_SUMMARY_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
COMBAT_SUMMARY_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
COMBAT_SUMMARY_LMSTUDIO = {"model": "local-model"}

# --- T030/T032/T033/T038/T066: DM Summarization (parsing, narration, safety, summaries) ---
# 24/24 synthetic tests passed. Mini-tier (DM_SUMMARIZATION_MODEL).
# T030: narrative parsing (JSON, temp=0.3). T032: travel narration (JSON, temp=0.8).
# T033: content safety (JSON, temp=0.1). T038: campaign saga (plain text, temp=0.6).
# T066: transition summary (plain text, temp=0.7).
# T038/T066 use response_format=None at callsite (plain text, not JSON).
DM_SUMM_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
DM_SUMM_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
DM_SUMM_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
DM_SUMM_LMSTUDIO = {"model": "local-model"}

# --- T039: Campaign export-data extraction (short JSON, mini tier) ---
# Secondary call inside _generate_module_summary that extracts structured
# campaign-relevant fields (relationships, artifacts, hubs, worldState,
# unlockedModules) from the human-readable saga produced by T038.
# JSON object output, temp=0.3 stays at callsite.
#
# Rationale for cheaper models than T038's sibling DM_SUMM_* group:
# T039 is a JSON-extraction task (data extraction from completed module summary).
# It runs AFTER T038 (saga generation) on T038's output, so the upstream summary
# is already AI-polished. Mini-tier models are sufficient because the task is
# structured-data extraction, not creative generation. These selections are
# starting points; capture testing should validate them later.
# TODO: Run capture comparison vs DM_SUMM_GPT54MINI_NONE / DM_SUMM_GEMINI_FLASH_LOW.
# The _T039_ segment disambiguates from T038's DM_SUMM_* group (different model/effort).
DM_SUMM_T039_GPT5MINI = {"model": "gpt-5-mini"}
DM_SUMM_T039_GEMINI_FLASHLITE_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low"}
DM_SUMM_T039_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
DM_SUMM_T039_LMSTUDIO = {"model": "local-model"}

# --- T012: Starting-location analysis helper (short JSON, mini tier) ---
# Called by _ai_analyze_starting_location in core/ai/action_handler.py when
# module integration needs to identify the best starting location for player
# arrival. Reads a structured module_data dict (areas, locations, NPCs, plot
# points) and emits a 5-field JSON object: locationId, locationName, areaId,
# areaName, reasoning. Temperature=0.1 stays at callsite (deterministic IDs).
#
# Rationale: structured extraction over already-structured data. The function
# itself has a deterministic fallback (_get_fallback_starting_location) when
# AI parsing fails, so this is a quality-of-life enhancer rather than a
# correctness-critical generator. Mini-tier models are appropriate.
# Initial selections mirror T039 (also a mini-tier JSON-extraction helper).
# TODO: Run capture comparison vs DM_SUMM_GPT54MINI_NONE / DM_SUMM_GEMINI_FLASH_LOW.
# T012: inline Gemini response_schema for starting-location analysis (no schema
# file fits). Without it, gemini-flash-lite drifts to narration and the code falls
# back to a degraded first-area location. Covers the fields action_handler reads.
_T012_STARTING_LOCATION_SCHEMA = {
    "type": "object",
    "properties": {
        "locationId": {"type": "string"},
        "locationName": {"type": "string"},
        "areaId": {"type": "string"},
        "areaName": {"type": "string"},
        "reasoning": {"type": "string"},
    },
}
DM_LOCSTART_T012_GPT5MINI = {"model": "gpt-5-mini"}
DM_LOCSTART_T012_GEMINI_FLASHLITE_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low", "response_schema": convert_to_gemini_schema(_T012_STARTING_LOCATION_SCHEMA)}
DM_LOCSTART_T012_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
DM_LOCSTART_T012_LMSTUDIO = {"model": "local-model"}

# --- T049: Storage action extraction (short JSON, mini tier) ---
# Called when a player issues a storage-related action (deposit, withdraw,
# transfer, view) on a container at a location. StorageProcessor uses an AI
# pass to translate the natural-language description into a structured JSON
# operation that the validator/schema layer then enforces. Temp=0.1 stays at
# the callsite (deterministic JSON extraction).
#
# Rationale: this is a constrained JSON-extraction task over already-known
# game state (character inventory, container contents). The downstream schema
# validator + retry loop (max_attempts=3 in storage_processor.process_storage_description)
# catches any malformed output, so a mini-tier model is correctness-safe.
# Initial selections mirror T012/T039 (other mini-tier JSON-extraction helpers).
# TODO: Run capture comparison once telemetry is collected on this callsite.
STORAGE_PROCESSOR_T049_GPT5MINI = {"model": "gpt-5-mini"}
STORAGE_PROCESSOR_T049_GEMINI_FLASHLITE_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low", "response_schema": _STORAGE_ACTION_SCHEMA_GEMINI}
STORAGE_PROCESSOR_T049_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
STORAGE_PROCESSOR_T049_LMSTUDIO = {"model": "local-model"}

# --- T015/T016/T018/T019: Adventure Summaries (location updates, chronicles, journals) ---
# 12/12 synthetic tests passed (4 scenarios x 3 models). Mini-tier (ADVENTURE_SUMMARY_MODEL).
# T015: location JSON update (temp=0.8). T016: adventure chronicle (temp=0.8, plain text).
# T018: concise location summary (temp=0.8, plain text). T019: expanded journal (temp=0.8, plain text).
# T016/T018/T019 use response_format=None at callsite (plain text, not JSON).
ADV_SUMM_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
ADV_SUMM_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
ADV_SUMM_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
ADV_SUMM_LMSTUDIO = {"model": "local-model"}

# --- T043/T044/T045: Combat Main Loop (scene setup, per-turn, resume) ---
# 100% on 16-criteria audit after V5 prompt (4/4 blind runs).
# Full-tier (COMBAT_MAIN_MODEL). Uses floating temperature from get_combat_temperature().
# gpt-5.4|none: best rules accuracy + narration. gemini-pro|low: best math transparency.
# gpt-5.2 DISQUALIFIED (hallucinated initiative orders).
# gemini-flash DISQUALIFIED (turn boundary violations, drops out-of-turn actions).
COMBAT_MAIN_GPT54_NONE = {"model": "gpt-5.4", "reasoning_effort": "none"}
COMBAT_MAIN_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
COMBAT_MAIN_LEGACY = {"model": "gpt-4.1-2025-04-14"}
COMBAT_MAIN_LMSTUDIO = {"model": "local-model"}

# ----- T085 Location Compression -----
# Compresses location JSON into token-based @-tag format for runtime context.
# Full-tier callsite, temperature=0.1, PLAIN TEXT output (response_format=None).
# Gemini-pro outputs JSON format instead of @-tags -- both work for downstream DM model.
# Gemini-flash NOT viable (too shallow on extraction).
LOC_COMPRESS_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none", "response_format": None}
LOC_COMPRESS_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low", "response_format": None}
LOC_COMPRESS_LEGACY = {"model": "gpt-4.1-2025-04-14", "response_format": None}
LOC_COMPRESS_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T020 Narrative Compression -----
# Compresses game conversation into 2-3 paragraph narrative summary.
# Mini-tier callsite, temperature=0.3, PLAIN TEXT output (response_format=None).
# gpt-5.4-mini|none = 5.0/5 avg, 2.7s. gemini-flash|low = 4.0/5, 3.1s.
NARR_COMPRESS_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none", "response_format": None}
NARR_COMPRESS_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low", "response_format": None}
NARR_COMPRESS_LEGACY = {"model": "gpt-4.1-mini-2025-04-14", "response_format": None}
NARR_COMPRESS_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T084 Agentic EVT Compression -----
# Compresses narrative into structured JSON with codebook + EVT beats.
# Mini-tier callsite, temperature=0.1, JSON output (default mode).
# gpt-5.4-mini|none = 4.0/5 avg, 2.1s. gemini-pro|low = 3.7/5, 10.9s.
# Gemini-flash NOT viable (too shallow on detail retention).
AGENTIC_COMPRESS_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
AGENTIC_COMPRESS_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
AGENTIC_COMPRESS_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
AGENTIC_COMPRESS_LMSTUDIO = {"model": "local-model"}

# --- T087/T088/T089/T090: DM_MINI_MODEL utility callsites ---
# NPC name canon (T087), NPC merge confirm (T088), prompt sanitizer (T089), quest formatter (T090).
# All mini-tier utility calls. Synthetic test: 12/12, 11/12, 5/5, 3/3 respectively.
# gpt-5.4-mini|none: best overall accuracy. gemini-flash|low: best on sanitization.
MINI_UTIL_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
MINI_UTIL_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}
MINI_UTIL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
# response_format:None -> do not force OpenAI json_object mode on LM Studio (local
# models frequently error on / mishandle it). T042 was confirmed broken without this.
# NOTE (systemic, follow-up): the same latent issue affects every other JSON-output
# *_LMSTUDIO config that lacks response_format:None (DM_FULL/DM_MINI/DM_VALIDATION/
# ACTION_PRED/CHAR_UPDATE/CHAR_EFFECTS/... ~25 configs). Validate against a real LM
# Studio server before adding it broadly; LM Studio is not part of capture testing.
# MINI_UTIL callsites include both structured and prose responses. Each callsite
# owns response_format explicitly (or intentionally uses the router's JSON
# default), so the shared Local config must not inject a second value.
MINI_UTIL_LMSTUDIO = {"model": "local-model"}

# --- T031+: DM_MAIN_MODEL callsites (module generation, DM narration, transitions) ---
# First DM_MAIN_MODEL migration (T031). These dicts will be reused by all 12 DM_MAIN_MODEL callsites.
# Full-tier. gpt-5.2|none: best creative generation. gemini-pro|low: highest quality at higher cost.
# Synthetic test: 5/5 all models on module field generation.
DM_MAIN_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
DM_MAIN_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
DM_MAIN_LEGACY = {"model": "gpt-4.1-2025-04-14"}
DM_MAIN_LMSTUDIO = {"model": "local-model"}

# T026 (location batch generation) -- per-callsite selection from the 2026-08-15
# blind 3-reviewer quality + cost eval (docs/audits/2026-08-15-t026-model-quality-eval.md).
# gpt-5.6-luna|high scored 28.3/30 (blind avg), BEATING gpt-5.2|none (26.3) at 1/12th
# the cost ($0.009 vs $0.114/build) and 2.4x faster. Retires gpt-5.2 for THIS callsite only;
# the other DM_MAIN callsites keep DM_MAIN_GPT52_NONE until separately evaluated.
# NOTE: high reasoning effort requires temperature=default(1); create_completion's
# _enforce_provider_constraints strips temperature automatically for gpt-5.x (non-mini)
# at reasoning > none, so the callsite passes temperature uniformly like every sibling.
# Reusable GPT-5.6 profiles.  Task-specific names below are detached compatibility
# aliases for older imports; canonical callsite selection lives in CALLSITE_BINDINGS.
OPENAI_GPT56_LUNA_NONE = {"model": "gpt-5.6-luna", "reasoning_effort": "none"}
OPENAI_GPT56_LUNA_LOW = {"model": "gpt-5.6-luna", "reasoning_effort": "low"}
OPENAI_GPT56_LUNA_MEDIUM = {"model": "gpt-5.6-luna", "reasoning_effort": "medium"}
OPENAI_GPT56_LUNA_HIGH = {"model": "gpt-5.6-luna", "reasoning_effort": "high"}
OPENAI_GPT56_TERRA_NONE = {"model": "gpt-5.6-terra", "reasoning_effort": "none"}
OPENAI_GPT56_TERRA_LOW = {"model": "gpt-5.6-terra", "reasoning_effort": "low"}
OPENAI_GPT56_TERRA_MEDIUM = {"model": "gpt-5.6-terra", "reasoning_effort": "medium"}
OPENAI_GPT56_TERRA_HIGH = {"model": "gpt-5.6-terra", "reasoning_effort": "high"}
OPENAI_GPT56_SOL_NONE = {"model": "gpt-5.6-sol", "reasoning_effort": "none"}
OPENAI_GPT56_SOL_LOW = {"model": "gpt-5.6-sol", "reasoning_effort": "low"}

DM_MAIN_T026_GPT56LUNA_HIGH = copy.deepcopy(OPENAI_GPT56_LUNA_HIGH)

# T104 (NPC cross-area role/attitude coherence reconciliation, issue #160) --
# classic-only, enabled at the reviewed tip (config.ENABLE_NPC_COHERENCE_REPAIR).
# One structured call over all repeated cross-area canonical identities. Focused
# semantic comparisons and a complete classic build selected Luna-none. Its OWN
# configs remain named for compatibility (do not reuse the T026 binding).
NPC_COHERENCE_T104_GPT56LUNA_NONE = copy.deepcopy(OPENAI_GPT56_LUNA_NONE)
# Historical import compatibility only; the canonical T104 binding is Luna-none.
NPC_COHERENCE_T104_GPT56LUNA_HIGH = copy.deepcopy(OPENAI_GPT56_LUNA_HIGH)
NPC_COHERENCE_T104_GEMINI_PRO_LOW = {"model": "gemini-3.1-pro-preview", "thinking_level": "low"}
NPC_COHERENCE_T104_LEGACY = {"model": "gpt-4.1-2025-04-14"}
NPC_COHERENCE_T104_LMSTUDIO = {"model": "local-model"}
# Feature flag (issue #160). Defined here so it reaches every build via config.py's
# `from model_config import *`, regardless of whether an existing config.py copy has
# it. ON: the pass is fail-closed + heal-forward so shipping enabled is safe.
ENABLE_NPC_COHERENCE_REPAIR = True

# ----- T105 NPC Voice (+ isolated affinity classifier) & T107 NPC Profile Seed -----
# Per-NPC "voice" micro-model agents (always on). These are per-NPC,
# per-relevant-turn micro calls, so OpenAI uses the CHEAPEST luna tier. Both the
# voice/affinity call (T105) and the one-time profile seed (T107) share the same
# cheap tier per provider. Temperature/output-cap stay at the callsite; the Gemini
# response_schema is supplied by the service from its own contract (kept out of here
# to avoid a model_config <-> core.npc import cycle). T105/T107 are distinct from
# main's T104 (NPC cross-area coherence), a different feature.
NPC_VOICE_T105_OPENAI_LUNA_NONE = copy.deepcopy(OPENAI_GPT56_LUNA_NONE)
NPC_VOICE_T105_GEMINI_FLASHLITE_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low"}
NPC_VOICE_T105_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
NPC_VOICE_T105_LMSTUDIO = {"model": "local-model"}

NPC_PROFILE_T107_OPENAI_LUNA_NONE = copy.deepcopy(OPENAI_GPT56_LUNA_NONE)
NPC_PROFILE_T107_GEMINI_FLASHLITE_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low"}
NPC_PROFILE_T107_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
NPC_PROFILE_T107_LMSTUDIO = {"model": "local-model"}

# T108: companion EPISODE extraction (attributed salient facts from full-fidelity
# encounter text -> canonical episode ledger). Runs at per-location close and at
# module-leave consolidation -- infrequent, quality-leaning within the luna tier.
# OpenAI on luna|LOW, designated after a real-archive sample (none/low/medium: all
# correct attribution + present-guard; low is the cost/quality balance). Final
# effort pending a blind 3-reviewer eval in the fine-tuning pass (cf. T026).
NPC_EPISODE_T108_OPENAI_LUNA_LOW = copy.deepcopy(OPENAI_GPT56_LUNA_LOW)
NPC_EPISODE_T108_GEMINI_FLASH_LOW = {"model": "gemini-3.1-flash-preview", "thinking_level": "low"}
NPC_EPISODE_T108_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
NPC_EPISODE_T108_LMSTUDIO = {"model": "local-model"}

# T112: episodic RECALL anchor-parse. When the player references the past, this
# parses their line into structured anchors (entities/places/outcomes); CODE then
# selects the matching episodeIds from the NPC's own index (the model never sees or
# selects episodes -> it cannot fabricate a memory). On-demand + cheap.
NPC_RECALL_T112_OPENAI_LUNA_LOW = copy.deepcopy(OPENAI_GPT56_LUNA_LOW)
NPC_RECALL_T112_GEMINI_FLASHLITE_LOW = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "low"}
NPC_RECALL_T112_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
NPC_RECALL_T112_LMSTUDIO = {"model": "local-model"}

# T113: episodic BACKFILL extraction. One-time, when upgrading an existing game to
# the episodic-memory feature: reads compressed journal / campaign-summary PROSE and
# selects the PRESENT companions from a CLOSED module roster (agentic presence,
# reconciled by code -- a name not in the roster is dropped) into attributed
# backfilled episodes. Same luna tier as T108; runs behind the upgrade progress UI.
NPC_BACKFILL_T113_OPENAI_LUNA_LOW = copy.deepcopy(OPENAI_GPT56_LUNA_LOW)
NPC_BACKFILL_T113_GEMINI_FLASH_LOW = {"model": "gemini-3.1-flash-preview", "thinking_level": "low"}
NPC_BACKFILL_T113_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
NPC_BACKFILL_T113_LMSTUDIO = {"model": "local-model"}

# --- Model Routing Settings ---
ENABLE_INTELLIGENT_ROUTING = True                        # Enable/disable action-based model routing
MAX_VALIDATION_RETRIES = 1                              # Retry with full model after this many validation failures

# --- Model Provider Selection ---
# Choose between cloud APIs (OpenAI/Gemini) or local LM Studio
# DEPRECATED: Use MODEL_PROVIDER instead. Kept for backwards compatibility during transition.
USE_LM_STUDIO = False                                   # Use local LM Studio on localhost:1234 (zero API costs)
                                                        # When True, all cloud model settings are ignored
                                                        # Requires LM Studio running with server started
                                                        # Direct connection - no proxy needed

# --- GPT-5 Model Configuration ---
GPT5_MINI_MODEL = "gpt-5-mini-2025-08-07"              # GPT-5 mini model for testing
GPT5_FULL_MODEL = "gpt-5-2025-08-07"                   # GPT-5 full model (kept for compatibility, not used)
# DEPRECATED: Use MODEL_PROVIDER instead. Kept for backwards compatibility during transition.
USE_GPT5_MODELS = False                                 # Toggle for GPT-5 models (default: GPT-4.1)
GPT5_USE_HIGH_REASONING_ON_RETRY = True                # Use high reasoning effort after first failure (instead of model switch)

# --- Combat System Settings ---
USE_COMPRESSED_COMBAT = True                            # Toggle for compressed combat AND validation prompts (False = original prompts)

# --- Conversation Compression Settings ---
# Enable/disable compression types before API calls
COMPRESSION_ENABLED = True                              # Master switch for all compression
COMPRESS_LOCATION_ENCOUNTERS = True                     # Compress location encounter data using dynamic compressor
COMPRESS_LOCATION_SUMMARIES = True                      # Compress location summaries (now implemented)

# --- Compression Model Configuration ---
# Models used for compressing conversation history and location data
NARRATIVE_COMPRESSION_MODEL = "gpt-4.1-mini-2025-04-14"  # For general narrative compression
LOCATION_COMPRESSION_MODEL = "gpt-4.1-2025-04-14"        # For location encounter compression
COMPRESSION_MAX_WORKERS = 4                              # Number of parallel workers for compression

# --- Text-to-Speech Configuration ---
TTS_MODEL = "tts-1"                                       # OpenAI TTS model (tts-1 or tts-1-hd for higher quality)
TTS_VOICE = "fable"                                       # Voice: alloy, echo, fable, onyx, nova, shimmer (fable is good for narration)
TTS_SPEED = 1.0                                           # Speed: 0.25 to 4.0 (1.0 is normal)
# --- Multi-Model Capture Settings ---
MULTI_MODEL_CAPTURE = False  # Set True to enable parallel cloud model testing (gpt-4.1, gpt-5.2, Gemini 3)
                             # Captures outputs to model_captures/ for comparison.
                             # MUST default False for production: when True it fans out 2 extra cloud
                             # calls per turn (added latency + cost) whenever a capture_config.json exists.
                             # Note: Ignored when MODEL_PROVIDER = "lmstudio" (LM Studio is production runtime, not for testing)

# --- Provider Selection ---
# Single setting replaces USE_GPT5_MODELS and USE_LM_STUDIO
# DEFAULT: "openai" -- the current, cost-optimized GPT-5.x callsite matrix
#   (gpt-5.6-luna / terra, with gpt-5.4 and gpt-5.2 retained where they win).
#   Set to "legacy" to run the stable gpt-4.1 / gpt-4.1-mini baseline instead;
#   "gemini" and "lmstudio" are also available. Switchable at runtime via
#   Settings -> AI Provider (persists in user_settings.json).
MODEL_PROVIDER = "openai"  # options: "openai" (default), "legacy", "gemini", "lmstudio"

PROVIDER_MODELS = {
    "legacy": {
        "full": "gpt-4.1-2025-04-14",
        "mini": "gpt-4.1-mini-2025-04-14",
    },
    "openai": {
        "full": "gpt-5.2",
        "mini": "gpt-5-mini",
    },
    "gemini": {
        "full": "gemini-3.1-pro-preview",
        "mini": "gemini-3.1-flash-lite-preview",
    },
    "lmstudio": {
        "full": "local-model",
        "mini": "local-model",
    },
}

# Per-callsite model variable overrides by provider.
# Populated from capture testing results. Each entry maps a task_id to the
# model variable name to use for each provider. Callsites NOT in this map
# use their original model variable unchanged.
# See docs/reference/legacy-model-variable-map.md for the full variable inventory.
CALLSITE_MODEL_MAP = {
    "T013": {
        "legacy":   "DM_MAIN_MODEL",    # gpt-4.1 (keep current behavior)
        "openai":   "DM_MINI_MODEL",    # gpt-5-mini
        "gemini":   "DM_MINI_MODEL",    # gemini-3.1-flash-lite
        "lmstudio": "DM_MINI_MODEL",    # local-model
    },
}

MODEL_TIER_MAP = {
    "DM_MAIN_MODEL": "full",
    "DM_VALIDATION_MODEL": "full",
    "DM_FULL_MODEL": "full",
    "COMBAT_MAIN_MODEL": "full",
    "CHARACTER_VALIDATOR_MODEL": "full",
    "NPC_BUILDER_MODEL": "full",
    "MONSTER_BUILDER_MODEL": "full",
    "LEVEL_UP_MODEL": "full",
    "ACTION_PREDICTION_MODEL": "full",
    "LOCATION_COMPRESSION_MODEL": "full",
    "DM_EFFECTS_MODEL": "full",
    "DM_MINI_MODEL": "mini",
    "DM_SUMMARIZATION_MODEL": "mini",
    "NARRATIVE_COMPRESSION_MODEL": "mini",
    "COMBAT_DIALOGUE_SUMMARY_MODEL": "mini",
    "ADVENTURE_SUMMARY_MODEL": "mini",
    "PLOT_UPDATE_MODEL": "mini",
    "PLAYER_INFO_UPDATE_MODEL": "mini",
    "NPC_INFO_UPDATE_MODEL": "mini",
    "ENCOUNTER_UPDATE_MODEL": "mini",
    "TRANSITION_VALIDATOR_MODEL": "mini",
}


def set_provider(provider_name):
    """Switch all model variables to the specified provider's models.

    Updates both model_config globals AND config module globals (since
    config.py uses 'from model_config import *' which creates snapshot
    bindings that won't see model_config changes otherwise).
    """
    global MODEL_PROVIDER
    if provider_name not in PROVIDER_MODELS:
        raise ValueError(f"Unknown provider: {provider_name}. Valid: {list(PROVIDER_MODELS.keys())}")
    MODEL_PROVIDER = provider_name
    models = PROVIDER_MODELS[provider_name]
    for var_name, tier in MODEL_TIER_MAP.items():
        globals()[var_name] = models[tier]
    # Also update config module if already imported (snapshot bindings)
    import sys
    if 'config' in sys.modules:
        config_mod = sys.modules['config']
        for var_name, tier in MODEL_TIER_MAP.items():
            if hasattr(config_mod, var_name):
                setattr(config_mod, var_name, models[tier])


def get_provider():
    """Return the current MODEL_PROVIDER, read live.

    HIGH-12 (#127): the sanctioned way to read the provider. All callsites use a
    DEFERRED `from model_config import MODEL_PROVIDER` inside the function body
    (executed per call), which reflects set_provider() live. Prefer this accessor
    in new code; NEVER add a module-level `from model_config import MODEL_PROVIDER`
    (it snapshots at import and goes stale on set_provider -- see the guard test).
    """
    return MODEL_PROVIDER


def get_model_for_callsite(task_id, default_var):
    """Get the correct model string for a callsite based on current provider.

    Looks up the task_id in CALLSITE_MODEL_MAP. If found, uses the
    provider-specific model variable. Otherwise falls back to default_var.

    Args:
        task_id: The callsite task ID (e.g., "T013")
        default_var: The default model variable name (e.g., "DM_MAIN_MODEL")

    Returns:
        The resolved model string for the current provider.
    """
    if task_id in CALLSITE_MODEL_MAP:
        var_name = CALLSITE_MODEL_MAP[task_id].get(MODEL_PROVIDER, default_var)
    else:
        var_name = default_var
    return globals()[var_name]


# Runtime entry points such as headless mode deliberately chdir into isolated
# game directories.  Provider selection belongs to the installation, not the
# campaign cwd, so always read the same ignored settings file the UI writes.
_USER_SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "user_settings.json")
_SECRET_SETTING_NAMES = {
    "openai_api_key": "openai_api_key",
    "gemini_api_key": "gemini_api_key",
    "local_api_key": "local_api_key",
}


def _load_user_settings():
    """Load user settings from disk. Returns empty dict if file doesn't exist."""
    if os.path.exists(_USER_SETTINGS_FILE):
        try:
            with open(_USER_SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_user_settings(settings):
    """Save non-secret settings to disk atomically with owner-only permissions."""
    tmp_path = _USER_SETTINGS_FILE + ".tmp"
    # Issue #134 class: O_BINARY keeps the CRT fd translation-free on Windows so
    # only the text wrapper below performs newline translation (without it, the
    # wrapper's \r\n is re-expanded to \r\r\n by the text-mode CRT layer).
    # POSIX: attr absent -> no-op.
    fd = os.open(
        tmp_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0),
        0o600,
    )
    with os.fdopen(fd, 'w') as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp_path, _USER_SETTINGS_FILE)
    try:
        os.chmod(_USER_SETTINGS_FILE, 0o600)
    except OSError:
        # Some Windows/WSL mounts do not implement POSIX permissions.
        pass


def _harden_settings_permissions():
    """Best-effort owner-only permissions on an existing settings file."""
    try:
        os.chmod(_USER_SETTINGS_FILE, 0o600)
    except OSError:
        # Some Windows/WSL mounts do not implement POSIX permissions.
        pass


def _migrate_plaintext_secrets(settings):
    """Move legacy JSON credentials into the OS credential store when one exists.

    A plaintext value is dropped from the JSON file ONLY after set_secret()
    confirms it is stored somewhere that outlives this process. With no OS
    credential store the fallback is memory-only, so the JSON copy is the only
    durable one and MUST stay -- removing it destroyed the user's saved key on
    the next restart (issue #129).
    """
    changed = False
    retained_plaintext = False
    for setting_name, secret_name in _SECRET_SETTING_NAMES.items():
        value = settings.get(setting_name)
        if not value:
            continue
        if set_secret(secret_name, value):
            settings.pop(setting_name, None)
            changed = True
        else:
            retained_plaintext = True
    if changed:
        _save_user_settings(settings)
    elif retained_plaintext:
        # This file holds the only durable copy, so make sure other accounts on
        # the machine cannot read it. _save_user_settings already does this on
        # the rewrite path.
        _harden_settings_permissions()
    return settings


def _read_credential(name):
    """Return a stored credential, preferring the OS store over the JSON copy."""
    return get_secret(name) or _load_user_settings().get(name)


def _store_credential(name, value):
    """Store a credential so it survives a restart, wherever that is possible.

    Uses the OS credential store when there is one and keeps plaintext out of
    the JSON file. Otherwise the JSON file IS the durable store, so the value
    is written there (owner-only, gitignored) rather than lost at exit.
    """
    settings = _load_user_settings()
    if set_secret(name, value):
        if settings.pop(name, None) is not None:
            _save_user_settings(settings)
        return
    settings[name] = value
    _save_user_settings(settings)


def _forget_credential(name):
    """Remove a credential from both the OS store and the JSON file."""
    delete_secret(name)
    settings = _load_user_settings()
    if settings.pop(name, None) is not None:
        _save_user_settings(settings)


def persist_provider(provider_name):
    """Save provider choice to disk so it survives restarts."""
    settings = _load_user_settings()
    settings["model_provider"] = provider_name
    _save_user_settings(settings)


def load_persisted_provider():
    """Load provider from disk and apply it. Call at startup.

    When the user has never explicitly chosen a provider, fall back to the
    application default "openai" (the cost-optimized GPT-5.x callsite matrix).
    An explicit choice saved via persist_provider() / the Settings panel always
    wins, so existing users who picked Legacy keep Legacy.
    """
    settings = _load_user_settings()
    provider = settings.get("model_provider", "openai")
    if provider in PROVIDER_MODELS:
        set_provider(provider)


DEFAULT_LOCAL_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LOCAL_API_KEY = "not-needed"


def get_local_endpoint():
    """Return the Local/Custom endpoint config without exposing stored secrets.

    Backward compatible: missing keys fall back to today's hard-coded LM Studio
    values. model == "" means 'keep each callsite's own model string'.
    """
    s = _migrate_plaintext_secrets(_load_user_settings())
    return {
        "base_url": s.get("local_base_url") or DEFAULT_LOCAL_BASE_URL,
        "api_key": _read_credential("local_api_key") or DEFAULT_LOCAL_API_KEY,
        "model": (s.get("local_model") or "").strip(),
    }


def persist_local_endpoint(base_url="", api_key=None, model=""):
    """Persist non-secret Local/Custom endpoint settings.

    api_key=None means KEEP the existing stored key -- the UI sends a blank key
    to mean "leave blank to keep" (and the field auto-clears after save), so a
    later URL/model save must NOT wipe a stored remote key. Pass a string to set
    it. base_url/model are always written (blank base_url falls back to the
    default; blank model means keep each callsite's own model).
    """
    s = _migrate_plaintext_secrets(_load_user_settings())
    s["local_base_url"] = (base_url or "").strip()
    s["local_model"] = (model or "").strip()
    _save_user_settings(s)
    if api_key is not None:
        _store_credential("local_api_key", api_key)


_OPENAI_KEY_PLACEHOLDER = "your_openai_api_key_here"


def persist_openai_key(api_key):
    """Store the OpenAI key durably: OS credential store when one exists."""
    _migrate_plaintext_secrets(_load_user_settings())
    if api_key:
        _store_credential("openai_api_key", api_key)
    else:
        _forget_credential("openai_api_key")


def has_openai_key():
    """True if a real (non-placeholder) OpenAI key is stored. Never returns the key."""
    key = _read_credential("openai_api_key")
    return bool(key) and key != _OPENAI_KEY_PLACEHOLDER


def apply_persisted_openai_key():
    """Push a stored OpenAI key into the live config module so every existing
    reader of config.OPENAI_API_KEY uses it with ZERO reader edits. No-op when
    no key is stored (config.py value wins). Mirrors set_provider's cross-module
    write via sys.modules['config'].
    """
    _migrate_plaintext_secrets(_load_user_settings())
    key = _read_credential("openai_api_key")
    if not key or key == _OPENAI_KEY_PLACEHOLDER:
        return
    import sys
    if "config" in sys.modules:
        setattr(sys.modules["config"], "OPENAI_API_KEY", key)


_GEMINI_KEY_PLACEHOLDER = "your_gemini_api_key_here"


def persist_gemini_key(api_key):
    """Store the Gemini key durably: OS credential store when one exists."""
    _migrate_plaintext_secrets(_load_user_settings())
    if api_key:
        _store_credential("gemini_api_key", api_key)
    else:
        _forget_credential("gemini_api_key")


def has_gemini_key():
    """True if a real (non-placeholder) Gemini key is stored. Never returns the key."""
    key = _read_credential("gemini_api_key")
    return bool(key) and key != _GEMINI_KEY_PLACEHOLDER


def apply_persisted_gemini_key():
    """Push a stored Gemini key into the live config module so every reader of
    config.GEMINI_API_KEY (the runtime Gemini client in
    utils/capture/gemini_caller._get_client) uses it with ZERO reader edits.
    No-op when no key is stored (config.py value wins). Mirrors
    apply_persisted_openai_key's cross-module write via sys.modules['config'].
    """
    _migrate_plaintext_secrets(_load_user_settings())
    key = _read_credential("gemini_api_key")
    if not key or key == _GEMINI_KEY_PLACEHOLDER:
        return
    import sys
    if "config" in sys.modules:
        setattr(sys.modules["config"], "GEMINI_API_KEY", key)


# Load persisted provider on import
load_persisted_provider()
# Best-effort: apply a stored OpenAI key if config is already loaded. The
# authoritative cold-start apply happens in web_interface.py startup and
# config_template.py (after config.py defines its default). No-op otherwise.
apply_persisted_openai_key()
apply_persisted_gemini_key()


# --- Canonical callsite resolver and capture compatibility view ---
def validate_model_registry():
    """Fail fast on missing profiles, invalid effort, or incomplete ladders."""
    errors = []
    from model_registry import EXPECTED_TASK_IDS

    if set(CALLSITE_BINDINGS) != set(EXPECTED_TASK_IDS):
        missing = sorted(set(EXPECTED_TASK_IDS) - set(CALLSITE_BINDINGS))
        unknown = sorted(set(CALLSITE_BINDINGS) - set(EXPECTED_TASK_IDS))
        errors.append(
            "binding inventory mismatch; missing=%s unknown=%s" % (missing, unknown)
        )
    for task_id, binding in CALLSITE_BINDINGS.items():
        if binding.task_id != task_id:
            errors.append("%s has mismatched task_id %s" % (task_id, binding.task_id))
        for provider in SUPPORTED_PROVIDERS:
            ladder = binding.profiles_for(provider)
            if not ladder:
                errors.append("%s/%s has no retry entry" % (task_id, provider))
                continue
            for profile_name in ladder:
                profile = globals().get(profile_name)
                if not isinstance(profile, dict) or not profile.get("model"):
                    errors.append(
                        "%s/%s references unknown profile %s"
                        % (task_id, provider, profile_name)
                    )
                    continue
                effort = profile.get("reasoning_effort")
                if effort is not None and effort not in (
                    "none",
                    "low",
                    "medium",
                    "high",
                    "xhigh",
                    "max",
                ):
                    errors.append(
                        "%s/%s profile %s has unsupported effort %s"
                        % (task_id, provider, profile_name, effort)
                    )
    if errors:
        raise RuntimeError("Invalid callsite model registry:\n- " + "\n- ".join(errors))
    return True


def resolve_callsite_config(task_id, provider=None, attempt=0):
    """Return a detached provider configuration for one zero-based attempt."""
    provider = provider or get_provider()
    try:
        binding = CALLSITE_BINDINGS[task_id]
    except KeyError as exc:
        raise KeyError("Unregistered model callsite: %s" % task_id) from exc
    ladder = binding.profiles_for(provider)
    try:
        attempt_index = int(attempt)
    except (TypeError, ValueError) as exc:
        raise ValueError("attempt must be a non-negative integer") from exc
    if attempt_index < 0:
        raise ValueError("attempt must be a non-negative integer")
    profile_name = ladder[min(attempt_index, len(ladder) - 1)]
    return copy.deepcopy(globals()[profile_name])


# Kept for callers/tests importing the historical name.  It is generated from
# the production registry, so capture and production selection cannot drift.
TASK_CAPTURE_CONFIGS = {
    task_id: (binding.openai[0], binding.gemini[0])
    for task_id, binding in CALLSITE_BINDINGS.items()
}


validate_model_registry()


def get_capture_variants_for_task(task_id):
    """Get per-callsite capture variants for a task_id.

    Returns list of variant dicts for use by capture system.
    Each dict has: provider, model, and provider-specific params.
    Returns None if task_id not mapped (falls back to tier-based).
    """
    if task_id not in CALLSITE_BINDINGS:
        return None  # Fall back to tier-based
    variants = []

    def openai_uses_caller_temperature(provider_config):
        model_name = str(provider_config.get("model", "")).lower()
        reasoning = str(provider_config.get("reasoning_effort", "")).lower()
        if "5-mini" in model_name:
            return False
        if "5.4-mini" in model_name:
            return not reasoning or reasoning == "none"
        if reasoning and reasoning != "none":
            return False
        return True

    # Get OpenAI variant
    openai_cfg = resolve_callsite_config(task_id, "openai")
    if openai_cfg:
        variant = {
            "provider": "openai",
            "model": openai_cfg.get("model"),
            "label": f"{openai_cfg.get('model')}|effort={openai_cfg.get('reasoning_effort', 'none')}",
            "use_caller_temp": openai_uses_caller_temperature(openai_cfg),
        }
        if "reasoning_effort" in openai_cfg:
            variant["reasoning_effort"] = openai_cfg["reasoning_effort"]
        if "response_format" in openai_cfg:
            variant["response_format"] = openai_cfg["response_format"]
        variants.append(variant)

    # Get Gemini variant
    gemini_cfg = resolve_callsite_config(task_id, "gemini")
    if gemini_cfg:
        variant = {
            "provider": "gemini",
            "model": gemini_cfg.get("model"),
            "label": f"{gemini_cfg.get('model')}|thinking={gemini_cfg.get('thinking_level', 'none')}",
            # Runtime intentionally leaves Gemini temperature unset.
            "use_caller_temp": False,
        }
        if "thinking_level" in gemini_cfg:
            variant["thinking_level"] = gemini_cfg["thinking_level"]
        if "response_schema" in gemini_cfg:
            variant["response_schema"] = gemini_cfg["response_schema"]
        if "response_format" in gemini_cfg:
            variant["response_format"] = gemini_cfg["response_format"]
        variants.append(variant)

    return variants if variants else None
