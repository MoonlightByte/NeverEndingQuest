# Model Configuration Settings
# This file contains all AI model configurations and can be safely committed to git
import json
import os


def convert_to_gemini_schema(json_schema):
    """Convert JSON Schema Draft-07 to Gemini API response_schema format.

    Strips $schema, required, oneOf (takes first option), uppercases types.
    Handles union types like ["integer", "null"] by taking the non-null type.
    Reusable for any callsite that needs Gemini response_schema forcing.
    """
    _TYPE_MAP = {
        "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
        "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
    }

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
            if "type" in first:
                result["type"] = _TYPE_MAP.get(first["type"], "STRING")
            if "items" in first:
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
        return result

    return {
        "type": "OBJECT",
        "properties": {
            k: _convert_prop(v) for k, v in json_schema.get("properties", {}).items()
        },
    }


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
DM_MINI_MODEL_GEMINI_FLASH_MINIMAL = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "minimal"}

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

# Gemini (3-flash with medium thinking -- capture tested: 4.93 quality, 5/5 correct)
DM_VALIDATION_GEMINI_FLASH_MEDIUM = {"model": "gemini-3-flash-preview", "thinking_level": "medium"}

# Legacy (no extra params)
DM_VALIDATION_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
DM_VALIDATION_LMSTUDIO = {"model": "local-model"}

# --- T082 Action Predictor Model Configs (from capture testing) ---
# Binary classifier, fires every turn. Speed and cost critical.
# Temperature is 0.1 at callsite.

# OpenAI (mini model with low reasoning -- 14/14 correct, $0.0007, 2.8s)
ACTION_PRED_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3-flash with minimal thinking -- 13/14 correct, $0.0011, 1.4s fastest)
ACTION_PRED_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}

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

# Gemini (3.1 flash-lite with minimal thinking + auto-converted schema)
CHAR_UPDATE_GEMINI_FLASHLITE_MINIMAL = {
    "model": "gemini-3.1-flash-lite-preview",
    "thinking_level": "minimal",
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

# ----- T046 Initiative Tracker -----
# Analytical combat utility: tracks turn order, determines who acts next.
# Full-tier callsite, temperature=0.1, plain text output.
# GPT-5.4 reviewer: gpt-5.2|none = 4/4 pass (4.2/5), gemini-flash|minimal = 4/4 pass (4.2/5)
# gpt-5-mini DISQUALIFIED (contradictory tracker on E[1], scored 1-2/5)

# OpenAI (gpt-5.2 with no reasoning -- 4/4 correct, 2.46s avg, temp=0.1 passes through)
INIT_TRACKER_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none", "response_format": None}

# Gemini (3-flash with minimal thinking -- 4/4 correct, 1.71s avg, fastest + cheapest)
INIT_TRACKER_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal", "response_format": None}

# Legacy (no extra params -- response_format=None opts out of default JSON mode)
INIT_TRACKER_LEGACY = {"model": "gpt-4.1-2025-04-14", "response_format": None}

# LM Studio (local passthrough)
INIT_TRACKER_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T078 Character Effects -----
# Analyzes character updates for trackable temporary effects (buffs/debuffs).
# Full-tier callsite, temperature=0.3, JSON output.
# GPT-5.4 reviewer: gpt-5.2|none = 5/5 pass (4.4/5), gemini-flash|high = 5/5 pass (4.4/5)
# gemini-flash|minimal scored 3/5 on Sneak Attack entry (contradictory duration metadata)

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

# OpenAI (gpt-5.4 with no reasoning -- 4/4 correct, 2.5s avg, temp=0.3 passes through)
COMBAT_VALID_GPT54_NONE = {"model": "gpt-5.4", "reasoning_effort": "none"}

# Gemini (3-flash with low thinking -- 4/4 correct, 1.6s avg, cheapest)
COMBAT_VALID_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# Legacy (no extra params)
COMBAT_VALID_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
COMBAT_VALID_LMSTUDIO = {"model": "local-model"}

# ----- T051 Character Validator -----
# Validates character AC calculations per 5e rules.
# Full-tier callsite, temperature=0.1, JSON output.
# GPT-5.4 reviewer: gpt-5.2|none = 3/3 pass (4.0/5), gemini-flash|minimal = 3/3 pass (4.3/5)
# Easy callsite -- all next-gen models pass. gpt-5.4-mini DISQUALIFIED (miscalculated Dex modifier)

# OpenAI (gpt-5.2 with no reasoning -- 3/3 correct, 6.0s avg, temp=0.1 passes through)
CHAR_VALIDATOR_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with minimal thinking -- 3/3 correct, 4.0s avg, fastest + cheapest)
CHAR_VALIDATOR_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}

# Legacy (no extra params)
CHAR_VALIDATOR_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
CHAR_VALIDATOR_LMSTUDIO = {"model": "local-model"}

# ----- T050 Effects / T054 Currency Gemini Config -----
# T050 effects categorization and T054 currency consolidation need gemini-flash|low
# (minimal fails on complex categorization and currency edge cases)
CHAR_VALIDATOR_GEMINI_FLASH_LOW = {"model": "gemini-3-flash-preview", "thinking_level": "low"}

# ----- T034 Monster Builder -----
# Creates monster stat blocks from name + party level.
# Full-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: gemini-flash|minimal = 3/3 pass (4.3/5), gpt-5.2|none = 3/3 pass (3.7/5)

# OpenAI (gpt-5.2 with no reasoning -- 3/3 correct, 5.1s avg, temp=0.7 passes through)
MONSTER_BUILD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with minimal thinking -- 3/3 correct, 2.7s avg, highest quality + cheapest)
MONSTER_BUILD_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}

# Legacy (no extra params)
MONSTER_BUILD_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
MONSTER_BUILD_LMSTUDIO = {"model": "local-model"}

# ----- T035 NPC Builder -----
# Creates full NPC character sheets from name + race/class/level.
# Full-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: gpt-5.2|none = 3/3 pass (4.0/5), gemini-flash|minimal = 3/3 pass (4.0/5)
# REQUIRES v4 prompt changes in npc_builder.py (name handling, equipment, racial traits)

# OpenAI (gpt-5.2 with no reasoning -- 3/3 correct, 34s avg, temp=0.7 passes through)
NPC_BUILD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}

# Gemini (3-flash with minimal thinking -- 3/3 correct, 10s avg, 3x faster + cheaper)
NPC_BUILD_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}

# Legacy (no extra params)
NPC_BUILD_LEGACY = {"model": "gpt-4.1-2025-04-14"}

# LM Studio (local passthrough)
NPC_BUILD_LMSTUDIO = {"model": "local-model"}

# ----- T081 Encounter Update -----
# Updates encounter creature data after combat actions.
# Mini-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: all models 3/3 pass. gemini-flash|minimal = 5.0/5 avg.
ENCOUNTER_UPD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
ENCOUNTER_UPD_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}
ENCOUNTER_UPD_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
ENCOUNTER_UPD_LMSTUDIO = {"model": "local-model"}

# ----- T077 Plot Update -----
# Updates plot progression after game events.
# Mini-tier callsite, temperature=0.7, JSON output.
# GPT-5.4 reviewer: all models 2/2 pass. gpt-5.2|none = 5.0/5 avg.
PLOT_UPD_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
PLOT_UPD_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}
PLOT_UPD_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
PLOT_UPD_LMSTUDIO = {"model": "local-model"}

# ----- T021 Transition Validation -----
# Validates location transitions (path blocking, encounter checks).
# Mini-tier callsite, temperature from TRANSITION_VALIDATOR_TEMPERATURE (0.3), JSON output.
# GPT-5.4 reviewer: all models 2/2 pass. gpt-5.2|none = 5.0/5 avg.
TRANSITION_VAL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
TRANSITION_VAL_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}
TRANSITION_VAL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
TRANSITION_VAL_LMSTUDIO = {"model": "local-model"}

# ----- T048 Level Up Validation -----
# Validates AI-generated level-up actions against 5e rules.
# Full-tier callsite, temperature=0.2, JSON output.
# 8/8 perfect on expanded synthetic tests (v4 prompt + leveling_info.txt).
# Uses gemini-3-PRO (not flash -- flash missed Barbarian wrong-die edge case)
LEVELUP_VAL_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
LEVELUP_VAL_GEMINI_PRO_LOW = {"model": "gemini-3-pro-preview", "thinking_level": "low"}
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
NPC_INFO_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}
NPC_INFO_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
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
DM_SUMMARY_GPT5MINI = {"model": "gpt-5-mini"}
DM_SUMMARY_GEMINI_FLASH_MINIMAL = {"model": "gemini-3.1-flash-lite-preview", "thinking_level": "minimal"}
DM_SUMMARY_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
DM_SUMMARY_LMSTUDIO = {"model": "local-model"}

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
COMBAT_MAIN_GEMINI_PRO_LOW = {"model": "gemini-3-pro-preview", "thinking_level": "low"}
COMBAT_MAIN_LEGACY = {"model": "gpt-4.1-2025-04-14"}
COMBAT_MAIN_LMSTUDIO = {"model": "local-model"}

# ----- T085 Location Compression -----
# Compresses location JSON into token-based @-tag format for runtime context.
# Full-tier callsite, temperature=0.1, PLAIN TEXT output (response_format=None).
# Gemini-pro outputs JSON format instead of @-tags -- both work for downstream DM model.
# Gemini-flash NOT viable (too shallow on extraction).
LOC_COMPRESS_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none", "response_format": None}
LOC_COMPRESS_GEMINI_PRO_LOW = {"model": "gemini-3-pro-preview", "thinking_level": "low", "response_format": None}
LOC_COMPRESS_LEGACY = {"model": "gpt-4.1-2025-04-14", "response_format": None}
LOC_COMPRESS_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T020 Narrative Compression -----
# Compresses game conversation into 2-3 paragraph narrative summary.
# Mini-tier callsite, temperature=0.3, PLAIN TEXT output (response_format=None).
# gpt-5.4-mini|none = 5.0/5 avg, 2.7s. gemini-flash|minimal = 4.0/5, 3.1s.
NARR_COMPRESS_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none", "response_format": None}
NARR_COMPRESS_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal", "response_format": None}
NARR_COMPRESS_LEGACY = {"model": "gpt-4.1-mini-2025-04-14", "response_format": None}
NARR_COMPRESS_LMSTUDIO = {"model": "local-model", "response_format": None}

# ----- T084 Agentic EVT Compression -----
# Compresses narrative into structured JSON with codebook + EVT beats.
# Mini-tier callsite, temperature=0.1, JSON output (default mode).
# gpt-5.4-mini|none = 4.0/5 avg, 2.1s. gemini-pro|low = 3.7/5, 10.9s.
# Gemini-flash NOT viable (too shallow on detail retention).
AGENTIC_COMPRESS_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
AGENTIC_COMPRESS_GEMINI_PRO_LOW = {"model": "gemini-3-pro-preview", "thinking_level": "low"}
AGENTIC_COMPRESS_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
AGENTIC_COMPRESS_LMSTUDIO = {"model": "local-model"}

# --- T087/T088/T089/T090: DM_MINI_MODEL utility callsites ---
# NPC name canon (T087), NPC merge confirm (T088), prompt sanitizer (T089), quest formatter (T090).
# All mini-tier utility calls. Synthetic test: 12/12, 11/12, 5/5, 3/3 respectively.
# gpt-5.4-mini|none: best overall accuracy. gemini-flash|minimal: best on sanitization.
MINI_UTIL_GPT54MINI_NONE = {"model": "gpt-5.4-mini", "reasoning_effort": "none"}
MINI_UTIL_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}
MINI_UTIL_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}
MINI_UTIL_LMSTUDIO = {"model": "local-model"}

# --- T031+: DM_MAIN_MODEL callsites (module generation, DM narration, transitions) ---
# First DM_MAIN_MODEL migration (T031). These dicts will be reused by all 12 DM_MAIN_MODEL callsites.
# Full-tier. gpt-5.2|none: best creative generation. gemini-pro|low: highest quality at higher cost.
# Synthetic test: 5/5 all models on module field generation.
DM_MAIN_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
DM_MAIN_GEMINI_PRO_LOW = {"model": "gemini-3-pro-preview", "thinking_level": "low"}
DM_MAIN_LEGACY = {"model": "gpt-4.1-2025-04-14"}
DM_MAIN_LMSTUDIO = {"model": "local-model"}

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
MULTI_MODEL_CAPTURE = True  # Set True to enable parallel cloud model testing (gpt-4.1, gpt-5.2, Gemini 3)
                             # Captures outputs to model_captures/ for comparison
                             # Note: Ignored when MODEL_PROVIDER = "lmstudio" (LM Studio is production runtime, not for testing)

# --- Provider Selection ---
# Single setting replaces USE_GPT5_MODELS and USE_LM_STUDIO
MODEL_PROVIDER = "legacy"  # options: "legacy", "openai", "gemini", "lmstudio"

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
    """Return the current MODEL_PROVIDER value."""
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


_USER_SETTINGS_FILE = "user_settings.json"


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
    """Save user settings to disk atomically."""
    tmp_path = _USER_SETTINGS_FILE + ".tmp"
    with open(tmp_path, 'w') as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp_path, _USER_SETTINGS_FILE)


def persist_provider(provider_name):
    """Save provider choice to disk so it survives restarts."""
    settings = _load_user_settings()
    settings["model_provider"] = provider_name
    _save_user_settings(settings)


def load_persisted_provider():
    """Load provider from disk and apply it. Call at startup."""
    settings = _load_user_settings()
    provider = settings.get("model_provider", "legacy")
    if provider in PROVIDER_MODELS:
        set_provider(provider)


# Load persisted provider on import
load_persisted_provider()


# --- Capture System Per-Callsite Model Configs ---
# Maps task_id -> (OpenAI config dict name, Gemini config dict name)
# Used by capture_and_fanout() to fire per-callsite variants instead of tier-based variants.
# Callsites not in this map fall back to tier-based variants from capture_config.json.
TASK_CAPTURE_CONFIGS = {
    # Full-tier callsites
    "T067": ("DM_FULL_MODEL_GPT52_NONE", "DM_FULL_MODEL_GEMINI_PRO_LOW"),
    "T065": ("DM_VALIDATION_GPT52_LOW", "DM_VALIDATION_GEMINI_FLASH_MEDIUM"),
    "T046": ("INIT_TRACKER_GPT52_NONE", "INIT_TRACKER_GEMINI_FLASH_MINIMAL"),
    "T078": ("CHAR_EFFECTS_GPT52_NONE", "CHAR_EFFECTS_GEMINI_FLASH_HIGH"),
    "T040": ("COMBAT_VALID_GPT54_NONE", "COMBAT_VALID_GEMINI_FLASH_LOW"),
    "T051": ("CHAR_VALIDATOR_GPT52_NONE", "CHAR_VALIDATOR_GEMINI_FLASH_MINIMAL"),
    "T034": ("MONSTER_BUILD_GPT52_NONE", "MONSTER_BUILD_GEMINI_FLASH_MINIMAL"),
    "T035": ("NPC_BUILD_GPT52_NONE", "NPC_BUILD_GEMINI_FLASH_MINIMAL"),
    "T048": ("LEVELUP_VAL_GPT52_NONE", "LEVELUP_VAL_GEMINI_PRO_LOW"),
    "T047": ("LEVELUP_CONV_GPT52_NONE", "LEVELUP_CONV_GEMINI_FLASH_LOW"),
    "T086": ("LEVELUP_CONV_GPT52_NONE", "LEVELUP_CONV_GEMINI_FLASH_LOW"),
    "T043": ("COMBAT_MAIN_GPT54_NONE", "COMBAT_MAIN_GEMINI_PRO_LOW"),
    "T044": ("COMBAT_MAIN_GPT54_NONE", "COMBAT_MAIN_GEMINI_PRO_LOW"),
    "T045": ("COMBAT_MAIN_GPT54_NONE", "COMBAT_MAIN_GEMINI_PRO_LOW"),
    "T085": ("LOC_COMPRESS_GPT52_NONE", "LOC_COMPRESS_GEMINI_PRO_LOW"),
    "T059": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T092": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),

    # Module generation (T022-T029, T031, T036-T037)
    "T022": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T023": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T024": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T025": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T026": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T028": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T029": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T031": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T036": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),
    "T037": ("DM_MAIN_GPT52_NONE", "DM_MAIN_GEMINI_PRO_LOW"),

    # Mini-tier callsites
    "T017": ("COMBAT_COMPRESS_GPT5MINI_LOW", "COMBAT_COMPRESS_GEMINI_FLASH_LOW"),
    "T079": ("CHAR_UPDATE_GPT5MINI_LOW", "CHAR_UPDATE_GEMINI_FLASHLITE_MINIMAL"),
    "T082": ("ACTION_PRED_GPT5MINI_LOW", "ACTION_PRED_GEMINI_FLASH_MINIMAL"),
    "T081": ("ENCOUNTER_UPD_GPT52_NONE", "ENCOUNTER_UPD_GEMINI_FLASH_MINIMAL"),
    "T077": ("PLOT_UPD_GPT52_NONE", "PLOT_UPD_GEMINI_FLASH_MINIMAL"),
    "T021": ("TRANSITION_VAL_GPT52_NONE", "TRANSITION_VAL_GEMINI_FLASH_MINIMAL"),
    "T014": ("NPC_INFO_GPT54MINI_NONE", "NPC_INFO_GEMINI_FLASH_MINIMAL"),
    "T091": ("NPC_INFO_GPT54MINI_NONE", "NPC_INFO_GEMINI_FLASH_MINIMAL"),
    "T041": ("COMBAT_SUMMARY_GPT54MINI_NONE", "COMBAT_SUMMARY_GEMINI_FLASH_LOW"),
    "T020": ("NARR_COMPRESS_GPT54MINI_NONE", "NARR_COMPRESS_GEMINI_FLASH_MINIMAL"),
    "T084": ("AGENTIC_COMPRESS_GPT54MINI_NONE", "AGENTIC_COMPRESS_GEMINI_PRO_LOW"),
    "T027": ("DM_SUMM_GPT54MINI_NONE", "DM_SUMM_GEMINI_FLASH_LOW"),

    # DM summarization (T030, T032, T033, T038, T066)
    "T030": ("DM_SUMM_GPT54MINI_NONE", "DM_SUMM_GEMINI_FLASH_LOW"),
    "T032": ("DM_SUMM_GPT54MINI_NONE", "DM_SUMM_GEMINI_FLASH_LOW"),
    "T033": ("DM_SUMM_GPT54MINI_NONE", "DM_SUMM_GEMINI_FLASH_LOW"),
    "T038": ("DM_SUMM_GPT54MINI_NONE", "DM_SUMM_GEMINI_FLASH_LOW"),
    "T066": ("DM_SUMM_GPT54MINI_NONE", "DM_SUMM_GEMINI_FLASH_LOW"),

    # Adventure summaries (T015, T016, T018, T019)
    "T015": ("ADV_SUMM_GPT54MINI_NONE", "ADV_SUMM_GEMINI_FLASH_LOW"),
    "T016": ("ADV_SUMM_GPT54MINI_NONE", "ADV_SUMM_GEMINI_FLASH_LOW"),
    "T018": ("ADV_SUMM_GPT54MINI_NONE", "ADV_SUMM_GEMINI_FLASH_LOW"),
    "T019": ("ADV_SUMM_GPT54MINI_NONE", "ADV_SUMM_GEMINI_FLASH_LOW"),

    # Mini utilities (T042, T063, T064, T087-T090, T093-T095)
    "T042": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T063": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T064": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T087": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T088": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T089": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T090": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T093": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T094": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
    "T095": ("MINI_UTIL_GPT54MINI_NONE", "MINI_UTIL_GEMINI_FLASH_MINIMAL"),
}


def get_capture_variants_for_task(task_id):
    """Get per-callsite capture variants for a task_id.

    Returns list of variant dicts for use by capture system.
    Each dict has: provider, model, and provider-specific params.
    Returns None if task_id not mapped (falls back to tier-based).
    """
    config_names = TASK_CAPTURE_CONFIGS.get(task_id)
    if not config_names:
        return None  # Fall back to tier-based

    openai_dict_name, gemini_dict_name = config_names
    variants = []

    # Get OpenAI variant
    openai_cfg = globals().get(openai_dict_name)
    if openai_cfg:
        variant = {
            "provider": "openai",
            "model": openai_cfg.get("model"),
            "label": f"{openai_cfg.get('model')}|effort={openai_cfg.get('reasoning_effort', 'none')}",
        }
        if "reasoning_effort" in openai_cfg:
            variant["reasoning_effort"] = openai_cfg["reasoning_effort"]
        variants.append(variant)

    # Get Gemini variant
    gemini_cfg = globals().get(gemini_dict_name)
    if gemini_cfg:
        variant = {
            "provider": "gemini",
            "model": gemini_cfg.get("model"),
            "label": f"{gemini_cfg.get('model')}|thinking={gemini_cfg.get('thinking_level', 'none')}",
        }
        if "thinking_level" in gemini_cfg:
            variant["thinking_level"] = gemini_cfg["thinking_level"]
        variants.append(variant)

    return variants if variants else None
