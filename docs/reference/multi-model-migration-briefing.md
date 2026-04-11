# Multi-Model Migration Briefing

**Date:** 2026-03-23
**Branch:** `multi-model-refactor`
**Status:** 40 of ~61 runtime callsites migrated

---

## What We Are Doing

Migrating NeverEndingQuest's AI callsites from hardcoded gpt-4.1 models to support multiple providers (OpenAI GPT-5.x, Google Gemini 3.x, LM Studio local). Each callsite gets per-provider model selection based on capture testing data.

## Architecture Pattern (CRITICAL -- read CLAUDE.md "Callsite Migration Pattern")

Each migrated callsite follows this exact pattern:

1. **Named config dicts in `model_config.py`** -- each bundles model string + provider-specific params (reasoning_effort, thinking_level, response_format, response_schema). Temperature is NEVER in the config dict -- it stays at the callsite.

2. **Callsite branches on `MODEL_PROVIDER`** -- deferred import inside the function (not module level) to pick up live provider switching from the web UI.

3. **Dict unpacking at the API call** -- `model=config["model"], **{k: v for k, v in config.items() if k != "model"}`

4. **`create_completion()` is a thin router** -- it does NOT inject params. No escalation ladder. Callsites own their params.

Example (from T067 in main.py):
```python
from model_config import MODEL_PROVIDER
if MODEL_PROVIDER == "openai":
    full_config = config.DM_FULL_MODEL_GPT52_NONE
    mini_config = config.DM_MINI_MODEL_GPT5MINI_LOW
elif MODEL_PROVIDER == "gemini":
    full_config = config.DM_FULL_MODEL_GEMINI_PRO_LOW
    mini_config = config.DM_MINI_MODEL_GEMINI_FLASH_MINIMAL
elif MODEL_PROVIDER == "lmstudio":
    full_config = config.DM_FULL_MODEL_LMSTUDIO
    mini_config = config.DM_MINI_MODEL_LMSTUDIO
else:  # legacy
    full_config = config.DM_FULL_MODEL_LEGACY
    mini_config = config.DM_MINI_MODEL_LEGACY

response = capture_and_fanout("T067", api_client.create_completion,
    messages=messages_to_send,
    model=selected_config["model"],
    temperature=TEMPERATURE,
    **{k: v for k, v in selected_config.items() if k != "model"})
```

## Key Infrastructure Changes Made

### Removed from `api_client.py`:
- **Blanket escalation ladder** -- was injecting reasoning_effort/thinking_level into EVERY call. Removed entirely. Callsites own their params.
- **`_ESCALATION_LADDERS` dict** and `_get_ladder_key()` function -- dead code removed.
- **`CALLSITE_OVERRIDES` merge block** -- removed. Import cleaned from model_config.

### Added to `api_client.py`:
- **`response_schema` handling** in `_gemini_completion()` -- pops from kwargs, forwards to `GenerateContentConfig`. Used by T079 for Gemini schema forcing.
- **gpt-5-mini reasoning_effort guard** in `_enforce_provider_constraints()` -- clamps `reasoning_effort="none"` to `"low"` for mini models (mini doesn't support "none").
- **Gemini 3.1 thinking allowlist** -- added `"gemini-3.1-pro"` and `"gemini-3.1-flash"` to `THINKING_SUPPORTED_MODELS` in `gemini_caller.py`.

### Added to `model_config.py`:
- **`convert_to_gemini_schema()`** -- converts JSON Schema Draft-07 to Gemini API format at runtime. Strips `$schema`, `required`, `oneOf`, uppercases types. Used by T079 to pass `char_schema.json` as Gemini `response_schema`.
- **Named config dicts** for each migrated callsite (see table below).
- **`_CHAR_SCHEMA_GEMINI`** -- auto-converted character schema loaded once at import time.

### Capture reviewer tool upgraded:
- `tools/capture_quality_reviewer.py` now uses **gpt-5.4 with reasoning_effort="medium"** (was gpt-4.1 which scored 5/12 on T065 validation -- too lenient).

---

## Completed Callsite Migrations

| Callsite | Description | File:Line | OpenAI Model | Gemini Model | Special Notes |
|---|---|---|---|---|---|
| T013 | Transition narration | action_handler.py:1005 | gpt-5-mini (via CALLSITE_MODEL_MAP) | gemini-3.1-flash-lite (via CALLSITE_MODEL_MAP) | Utility call, never shown to player. Uses old CALLSITE_MODEL_MAP pattern (pre-config-dict). |
| T067 | Main DM loop | main.py:2333 | gpt-5.2 none / gpt-5-mini low | gemini-3.1-pro low / gemini-3.1-flash-lite minimal | Dynamic model selection (full/mini per turn via intelligent routing). Two configs per provider. |
| T065 | AI response validation | main.py:1239 | gpt-5.2 low | gemini-3-flash medium | gpt-5.2\|none is UNUSABLE for validation (0/15 correct). Validation needs reasoning. |
| T082 | Action predictor (router) | action_predictor.py:161 | gpt-5-mini low | gemini-3-flash minimal | Binary classifier, fires every turn. Speed critical. Dead OpenAI client removed. |
| T079 | Character data updates | update_character_info.py:1446 | gpt-5-mini low | gemini-3.1-flash-lite minimal + response_schema | Gemini needs `response_schema` (auto-converted from char_schema.json) to prevent narration output. Dead code removed (get_model_for_character, OpenAI client, model imports). |
| T017 | Combat compression | combat_compression_engine.py:176 | gpt-5-mini low | gemini-3-flash low + response_format=None | Plain text tag output (NOT JSON). Must pass response_format=None to opt out of default JSON mode. Prompt improved (v5) with PLAYER TURN, ROUND COMPLETE, @STATUS rules. |
| T046 | Initiative tracker | initiative_tracker_ai.py:177 | gpt-5.2 none | gemini-3-flash minimal | Analytical utility, temp=0.1. Plain text output (response_format=None). gpt-5-mini DISQUALIFIED (contradictory tracker). Dead OpenAI client removed. |
| T078 | Character effects | update_character_effects.py:210 | gpt-5.2 none | gemini-3-flash high | JSON output (should_track + effect). flash|minimal scored 3/5 (Sneak Attack duration bug). Dead OpenAI client + hasattr fallback removed. |
| T040 | Combat validation | combat_manager.py:796 | gpt-5.4 none | gemini-3-flash low | FIRST gpt-5.4 callsite (5.2 fails validation). Requires v4 prompt fixes to combat_validation_prompt_compressed.txt. v4 changes are generic and backwards-compatible with gpt-4.1. |
| T051 | Character validator | character_validator.py:1050 | gpt-5.2 none | gemini-3-flash minimal | AC validation math. Easy callsite, all models pass. gpt-5.4-mini DISQUALIFIED (miscalculated Dex modifier). Shared self.client preserved for T052-T054. |
| T034 | Monster builder | monster_builder.py:190 | gpt-5.2 none | gemini-3-flash minimal | Creative generation, temp=0.7. Gemini scores higher (4.3 vs 3.7). Dead OpenAI client removed. |
| T035 | NPC builder | npc_builder.py:149 | gpt-5.2 none | gemini-3-flash minimal | Creative generation, temp=0.7. v4 prompt fixes (name handling, equipment, racial traits). Dead OpenAI client removed. |
| T050 | Effects categorizer | character_effects_validator.py:344 | gpt-5.2 none | gemini-3-flash low | Categorizes effects into temporaryEffects/injuries/removed. gemini-flash|minimal fails (1/3). Dead OpenAI client removed. |
| T052 | Inventory validator | character_validator.py:1137 | gpt-5.2 none | gemini-3-flash minimal | Inventory item categorization. Easy callsite. |
| T053 | Batched validator | character_validator.py:1733 | gpt-5.2 none | gemini-3-flash minimal | Combines AC + inventory + currency + class features in one call. |
| T054 | Currency consolidation | character_validator.py:2138 | gpt-5.2 none | gemini-3-flash low | v3 prompt fixes (magical ammo exclusion, electrum, trade goods). gemini-flash|minimal fails edge cases. Dead OpenAI client removed from shared class. |
| T047 | Level-up conversation | level_up_manager.py:212 | gpt-5.2 none | gemini-3-flash low | Interactive interview, temp=0.7. v3 prompt (greeting+HP combined, subclass HP bonuses, NPC auto-path). Dead OpenAI client removed. |
| T086 | NPC auto-level-up | level_up.py:110 | gpt-5.2 none | gemini-3-flash low | Single-shot JSON, temp=0.3. Reuses LEVELUP_CONV configs. Dead OpenAI client removed. |
| T014 | NPC movement decision | action_handler.py:2026 | gpt-5.4-mini none | gemini-3-flash minimal | Background NPC remove/update_status/move. temp=0.7. Function-local client deleted. |
| T091 | Monster reconciliation | reconcile_location_state.py:144 | gpt-5.4-mini none | gemini-3-flash minimal | Prunes killed/fled monsters. temp=0.2. response_format=None (JSON array). Dead client removed. |
| T041 | Combat dialogue summary | combat_manager.py:1037 | gpt-5.4-mini none | gemini-3-flash low | Creative narrative summary, temp=0.8. v2 prompt (no markdown, 150-250 words, ASCII only). response_format=None. Shared client preserved. |

## Key Findings from Testing

### Model behavior differences:
- **gpt-5.2\|none** is the best for narration/DM tasks (T067) but UNUSABLE for validation (T065: 0/15 correct). Validation needs reasoning.
- **gpt-5-mini\|low** is the workhorse -- good balance of cost, speed, and accuracy for most callsites.
- **gpt-5-mini\|minimal** is cheaper/faster but inconsistent on complex tasks.
- **gpt-5-mini\|medium** is almost always worse than low -- slower with no quality gain, sometimes worse (T017: 0/6).
- **gemini-3-flash** models are fast and cheap but need guidance -- without `response_schema` they output wrong JSON structures (T079 narration problem), and without `response_format=None` they wrap plain text in JSON (T017).
- **gemini-3-pro** models are expensive and surprisingly bad at some tasks (T067: worst performer, hallucinated plot details).

### Gemini-specific patterns:
- **`response_schema`** from `char_schema.json` (auto-converted) prevents Gemini from outputting narration JSON on structured callsites. The `convert_to_gemini_schema()` function handles this at import time.
- **`response_format=None`** is required for plain text callsites (T017 compression). Without it, default JSON mode wraps tags in `{}`.
- **Thinking levels** (minimal/low/medium/high) have inconsistent impact -- sometimes minimal=low in quality, sometimes low is significantly better (T017 stability).
- **`model_supports_thinking()`** allowlist needed updating for gemini-3.1 models (substring matching fixed).

### Temperature handling:
- **Legacy/LM Studio:** temperature passes through normally.
- **OpenAI gpt-5.2 reasoning=none:** temperature passes through (only reasoning level that supports it).
- **OpenAI gpt-5.2 reasoning>none:** `_enforce_provider_constraints` strips temperature.
- **OpenAI gpt-5-mini:** temperature ALWAYS stripped (mini never supports it).
- **Gemini:** temperature silently ignored in `_gemini_completion()` (Gemini optimized for 1.0).

### Prompt changes:
- **T017 combat compression** -- v5 prompt improvements committed. Added explicit rules for PLAYER TURN (@PROCESS = player only), ROUND COMPLETE (@PROCESS = all acted), @STATUS precedence (dead > acted > after_player > waiting), @ATK mandatory with player:[] convention. These changes are backwards-compatible with gpt-4.1-mini.
- **All other callsites** -- prompts frozen per project rules. No changes.

## Testing Process

### Capture testing (game play data):
1. Play the game with `MULTI_MODEL_CAPTURE = True` in `model_config.py`
2. Captures go to `model_captures/TXXX.json` (per callsite)
3. Run `tools/capture_quality_reviewer.py TXXX` to get GPT-5.4 scored quality reviews
4. Always run ALL entries, report correctness as X/Y where Y = total entries tested

### Synthetic testing (artificial prompts):
1. Load captured prompts from `model_captures/TXXX.json`
2. Replay through candidate models with controlled params
3. Scripts saved to `tests/model_validation/test_tXXX_*.py`
4. Dispatch sonnet agents to review output accuracy against baseline

### Correctness reporting:
- The denominator is ALWAYS the total number of test runs, never a subset
- GPT-5.4 reviewer (medium reasoning) is the judge -- upgraded from gpt-4.1 which was too lenient
- Live replay tests (running actual prompts through models) take precedence over reviewer opinion

## Files Modified (Not Pushed)

7 commits on `multi-model-refactor` branch:

```
6358aae feat: migrate T017 combat compression to per-provider model configs
4964dd1 feat: migrate T079 character updates to per-provider model configs
a90b09d feat: migrate T082 action predictor to per-provider model configs
79672fd feat: upgrade capture reviewer to gpt-5.4 + add model validation tests
f2ab803 feat: migrate T065 validation to per-provider model configs
9f7116a feat: migrate T067 to per-provider model configs + infrastructure fixes
d7d21ba fix: handle response_format=None in capture variants and Gemini path
```

Key files changed:
- `core/ai/api_client.py` -- thin router, response_schema support, constraint guards
- `model_config.py` -- all config dicts, convert_to_gemini_schema(), schema loading
- `main.py` -- T067 and T065 callsite wiring
- `utils/action_predictor.py` -- T082 callsite wiring
- `updates/update_character_info.py` -- T079 callsite wiring
- `core/ai/combat_compression_engine.py` -- T017 callsite wiring + v5 prompt
- `utils/capture/gemini_caller.py` -- 3.1 thinking allowlist
- `tools/capture_quality_reviewer.py` -- upgraded to gpt-5.4
- `tests/test_create_completion_integration.py` -- 16 tests, escalation tests removed
- `tests/model_validation/` -- synthetic test scripts (4 scripts)
- `CLAUDE.md` -- migration pattern, reviewer rules, response_schema docs

## Remaining Callsites with Capture Data

All callsites with capture data have been migrated. Remaining ~50 callsites need gameplay sessions to collect capture data.

## Remaining Callsites Without Capture Data

Need more game play sessions to collect data. See `docs/reference/legacy-model-variable-map.md` for the full inventory (~54 remaining callsites).

## Reference Documents

- `CLAUDE.md` -- "Callsite Migration Pattern" section has the full pattern with code examples
- `docs/reference/legacy-model-variable-map.md` -- all 21 model variables, callsite counts, DONE markers
- `docs/reference/capture-report-template.md` -- standardized report format
- `docs/reference/openai-models-reference.md` -- GPT-5.x specs, reasoning_effort values
- `docs/reference/gemini-models-reference.md` -- Gemini 3.x specs, thinking_level values
- `tests/model_validation/README.md` -- master migration status table + test script index
- `docs/issues/t079-gemini-schema-forcing.md` -- background on Gemini response_schema need

## Known Issues

1. **T039 bug** -- `campaign_manager.py:564` references `config.DM_SUMMARY_MODEL` which doesn't exist in model_config.py. Should be `config.DM_SUMMARIZATION_MODEL`. Latent crash if this code path executes.
2. **T013 uses old pattern** -- wired with `CALLSITE_MODEL_MAP` + `get_model_for_callsite()` instead of the config-dict pattern. Should be migrated to match T067+ pattern eventually.
3. **Capture config sync** -- testing folder (`dungeon_master_v1_testing`) and main repo have different `capture_config.json` files. Main repo has gpt-5.4 variants, testing folder doesn't. Need to reconcile before next play session.
4. **gemini-3.1 capture data** -- no 3.1 model data collected yet. Capture config was updated in testing folder to include 3.1 variants for next session.

## Bugs Found During Live Gameplay (2026-04-10)

### Startup Resume: Blank Screen on Game Restart

**Commits:** `9c6a8ee`, `4f8d67a`

**Root cause:** The startup lease system (`startup_state.json`) persisted `status: "kickoff_done"` across game sessions with no reset mechanism. On every subsequent restart, `claim_kickoff_lease()` returned "already_done", causing `_run_startup_kickoff_once()` to return early at line 261 WITHOUT calling `process_ai_response()`. The precomputed DM response (generated from the "player has returned" injection) was silently discarded.

**Fix:** Call `issue_new_attempt_id()` at the top of `main_game_loop()` to reset the lease state to `wizard_complete` before each session. Also removed the previous "CRITICAL FIX" block (dead code after the reset) and added a safety net fallback.

**Secondary issue:** DM narration during startup was sent to the web client as type `'startup'` instead of `'narration'`. The client-side JavaScript renders `'startup'` messages as plain unstyled text (same path as system/error messages) -- no avatar, no header, no "Generate Image" button. Fixed by always typing DM content as `'narration'` in `_flush_dm_buffer()`.

### T079: NameError Breaks ALL Character Updates

**Commit:** `0000d6f`

**Root cause:** The T079 migration (commit `4964dd1`) removed `get_model_for_character()` and its call `model = get_model_for_character(character_role)`, replacing it with the `char_update_config` dict pattern. However, line 1503 in `update_character_info.py` still referenced the now-undefined `model` variable in a debug logging dict:

```python
debug_data = {
    ...
    "model_used": model,   # NameError: 'model' is not defined
    ...
}
```

This `NameError` occurred AFTER the API call succeeded and AFTER the correct response was extracted, but BEFORE the delta was merged and saved. The generic `except Exception` handler caught it, retried 3 times (burning 3 API credits each time), then returned `False`. The calling code in `main.py` silently ignored `False` returns from the concurrent executor.

**Impact:** ALL character updates were broken on ALL providers -- gold transfers, inventory changes, HP modifications, condition updates. Every `updateCharacterInfo` action from the DM was silently dropped.

**Fix:** One-line change: `"model_used": model` -> `"model_used": char_update_config["model"]`.

**Why capture testing didn't catch it:** The capture system tests the API call (does the model return valid JSON?). The `NameError` is in the Python plumbing AFTER the API call -- pure code that no capture test exercises. A grep for all references to the old `model` variable after removing `get_model_for_character()` would have caught this instantly.

**Lesson:** After removing any function/variable during migration, grep the entire file for remaining references to the deleted name. Add this to the migration checklist.
