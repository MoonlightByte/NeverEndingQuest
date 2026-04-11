# Multi-Provider Model Migration: Approach, Methodology, and Findings

**Project:** NeverEndingQuest AI Dungeon Master
**Date:** April 2026
**Branch:** `multi-model-refactor`
**Status:** 64 of ~64 runtime callsites migrated (100%)

---

## 1. Executive Summary

NeverEndingQuest is an AI-powered D&D 5e Dungeon Master system with 61+ runtime API callsites. All originally used OpenAI's `gpt-4.1` family (being sunset). This migration adds multi-provider support: OpenAI GPT-5.x, Google Gemini 3.x, and LM Studio (local), letting players choose their AI provider through the web UI.

Each callsite was individually analyzed, synthetically tested, quality-reviewed by GPT-5.4, and migrated with provider-specific model selections. The process uncovered that **no single model works for all callsites** -- validation tasks need different models than creative generation, compression needs different models than NPC building. 22+ game prompts required surgical modifications to work with next-gen models.

**Key outcomes:**
- 64 callsites migrated across all 21 model variables (100% complete)
- 22+ prompt improvements committed (all backwards-compatible with gpt-4.1)
- ASCII standardization rules added to every creative/narrative prompt
- 5 distinct OpenAI models used: gpt-5.2|none (full-tier creative/analytical), gpt-5.4|none (combat), gpt-5.4-mini|none (mini-tier utility/narration), gpt-5-mini|low (speed-critical routing), gpt-5.2|low (validation)
- 3 distinct Gemini models used: gemini-3-flash|minimal (simple utility), gemini-3-flash|low (narration/summarization), gemini-3-pro|low (creative generation/combat/schema-heavy tasks)
- 8 dead OpenAI clients deleted across 8 files (all shared and function-local clients removed)
- Module generation pipeline fully traced and tested (T022-T029 sequential workflow)
- Intelligent model tier selection: full-tier for accuracy-critical tasks, mini-tier downgrade for pure narration
- gpt-5.4 was needed for combat (main loop + validation) -- 5.2 hallucinated initiative orders
- gpt-5.4-mini emerged as the workhorse for mini-tier callsites (12 callsites)
- gemini-flash was disqualified for combat (turn boundary violations)
- gemini-pro was required for combat, level-up validation, and compression tasks
- 16-criteria combat quality audit developed with blind agent reviews
- ASCII/no-markdown prompt rules standardized across all narrative callsites

---

## 2. Architecture

### 2.1 The Pattern

Every migrated callsite follows the same pattern:

```python
# Named config dict in model_config.py
CALLSITE_GPT52_NONE = {"model": "gpt-5.2", "reasoning_effort": "none"}
CALLSITE_GEMINI_FLASH_MINIMAL = {"model": "gemini-3-flash-preview", "thinking_level": "minimal"}
CALLSITE_LEGACY = {"model": "gpt-4.1-2025-04-14"}
CALLSITE_LMSTUDIO = {"model": "local-model"}

# Callsite branches on provider
from model_config import MODEL_PROVIDER
if MODEL_PROVIDER == "openai":
    cfg = config.CALLSITE_GPT52_NONE
elif MODEL_PROVIDER == "gemini":
    cfg = config.CALLSITE_GEMINI_FLASH_MINIMAL
elif MODEL_PROVIDER == "lmstudio":
    cfg = config.CALLSITE_LMSTUDIO
else:  # legacy
    cfg = config.CALLSITE_LEGACY

response = api_client.create_completion(
    messages=messages,
    model=cfg["model"],
    temperature=TEMP,  # stays at callsite
    **{k: v for k, v in cfg.items() if k != "model"})
```

### 2.2 Key Design Decisions

- **Temperature stays at the callsite**, never in the config dict. This preserves callsite-specific tuning.
- **`create_completion()` is a thin router** -- it routes to OpenAI/Gemini/LMStudio but does NOT inject parameters. Callsites own their params.
- **Deferred `MODEL_PROVIDER` import** inside function bodies (not module level) so the web UI can switch providers at runtime.
- **`response_format=None`** opts out of default JSON mode for plain-text callsites (T017, T046, T020, T085).
- **`response_schema`** (auto-converted from JSON Schema) forces Gemini to output correct structure on T079.
- **Each callsite gets its own tested config dicts** -- no blanket "use gpt-5.2 everywhere."

### 2.3 The `_UNSET` Sentinel

`api_client.py` uses a sentinel pattern for `response_format`:
- `_UNSET` (default) = apply JSON mode
- `None` (explicit) = plain text, no JSON mode
- `{"type": "json_object"}` (dict) = explicit JSON mode

This distinction is critical because some callsites output plain text (@-tag compression, narrative summaries) while most output JSON.

---

## 3. Synthetic Testing Methodology

### 3.1 Why Synthetic Testing

Real gameplay captures were only available for 11 callsites (from prior play sessions). The remaining ~50 needed synthetic test construction. We developed a methodology to simulate realistic API inputs without requiring actual gameplay.

### 3.2 The Process

For each callsite:

1. **Read the callsite code** -- dispatch an agent to read the full function, system prompt, user message construction, temperature, and response format.

2. **Construct synthetic scenarios** -- build 2-8 test inputs covering:
   - Happy path (correct/valid inputs)
   - Edge cases (ties, missing data, boundary conditions)
   - Error cases (wrong math, invalid features, fabricated data)
   - Class variety (Rogue, Fighter, Cleric, Wizard, Barbarian, Ranger)

3. **Run candidate models** -- test 4-8 model variants:
   - gpt-4.1 baseline (reference)
   - gpt-5.2|none (primary OpenAI candidate)
   - gpt-5.4|none (for validation callsites)
   - gpt-5.4-mini|none (for mini-tier cost optimization)
   - gpt-5-mini|low (mini workhorse, but no temperature support)
   - gemini-3-flash|minimal (fast/cheap Gemini)
   - gemini-3-flash|low (more thinking for complex tasks)
   - gemini-3-pro|low (for hard callsites where flash fails)

4. **Score with GPT-5.4 reviewer** -- `tools/capture_quality_reviewer.py` sends the full prompt + all model outputs to GPT-5.4 (reasoning=medium) for qualitative scoring on 6 criteria (1-5 each):
   - Instruction Compliance
   - Content Accuracy
   - Completeness
   - Narrative Quality
   - Contextual Awareness
   - Schema Correctness

5. **Validate with independent agents** -- dispatch blind agents to read inputs and outputs without seeing other models' verdicts. This caught cases where the GPT-5.4 reviewer was wrong (T040 combat validation -- reviewer rewarded false rejections).

6. **Iterate on prompts** -- when models fail, analyze WHY and make targeted, model-agnostic prompt improvements. Test again. Loop until reliable.

### 3.3 Critical Rule: No Python-Based Scoring

Early in the project, we used Python to check model outputs (e.g., `verdict == True`). This was wrong -- hardcoded checks can't evaluate nuanced D&D rules compliance. The rule was established: **all quality scoring must go through the GPT-5.4 reviewer or independent agent assessment**. Python is only used to collect outputs and measure latency.

### 3.4 Ground Truth Verification

The GPT-5.4 reviewer is not infallible. On T040 (combat validation), the reviewer scored the baseline 1/5 and gpt-5.2 4/5. Independent blind agents proved the baseline was correct (4/4) and gpt-5.2 was wrong (0/4 -- false rejections). The reviewer had been rewarding aggressive validators without understanding the D&D rules.

**Lesson:** Always verify ground truth independently on validation callsites. The reviewer judges output quality, not correctness of yes/no decisions.

---

## 4. Model Behavior Findings

### 4.1 OpenAI GPT-5.2

**Strengths:** Best overall quality for narration, DM tasks, and structured output. Follows complex @-tag compression formats. Good at preserving mechanical details.

**Weaknesses:** Over-validates on validation callsites (T065: 0/15 correct, T040: 0/4 correct without prompt fixes). With `reasoning_effort > none`, temperature is stripped (API constraint). More expensive than mini models.

**Best for:** Narration (T067), creative generation (T034, T035), compression (T085), structured output (T046, T078, T051).

### 4.2 OpenAI GPT-5.4

**Strengths:** Better than 5.2 for validation and combat tasks. Only model with zero critical failures on the 16-criteria combat audit. Correctly handles out-of-turn player action deferral (@HOLDING rules). Does not hallucinate game state (unlike 5.2 which fabricated initiative orders). Supports temperature with reasoning=none.

**Weaknesses:** 40% more expensive than 5.2. Slower on combat (6-9s vs 3-5s for baseline). On T048 level-up validation, it has a "valid bias" bug. Plan field can be terse (omits explicit dice math).

**Best for:** Combat main loop (T043/T044/T045), combat validation (T040). The go-to model for any callsite requiring strict rules compliance and turn-by-turn accuracy.

### 4.3 OpenAI GPT-5.4-mini

**Discovered mid-migration** as a cost-effective option. Unlike gpt-5-mini, it supports `reasoning_effort="none"` AND temperature -- making it viable for mini-tier callsites that need temperature control.

**Strengths:** Fast (1.5-3s), cheap (mini pricing), supports temperature with none reasoning. Scored 5/5 on narrative compression (T020) and 4/5 on agentic compression (T084).

**Weaknesses:** Inconsistent on validation (2/3 on T050, miscalculated Dex modifier on T051). Not suitable for complex validation or combat tasks.

**Best for:** Narrative compression (T020), agentic compression (T084) -- mini-tier creative tasks.

### 4.4 OpenAI GPT-5-mini

**Weaknesses that limit usage:** Does NOT support `reasoning_effort="none"` (only low/medium/high). Does NOT support temperature at ANY reasoning level. This makes it unusable for any callsite that needs temperature control.

**Where it works:** T082 action predictor (no temperature needed, speed critical). T017 combat compression (via reasoning=low, no temperature).

### 4.5 Gemini 3 Flash

**Strengths:** Fastest model (1-3s), cheapest ($0.50/1M input, $3/1M output), good for simple structured tasks. Excellent on inventory categorization (T052), plot updates (T077), encounter updates (T081).

**Weaknesses:** Too shallow for complex tasks -- drops mechanical details, fabricates data on compression tasks, can't handle 60K+ character inputs reliably. Struggles with specialized formats (@-tag notation, EVT blocks).

**Best for:** Simple JSON tasks (T052, T077, T081, T021, T082), character effects (T078 with high thinking), initiative tracking (T046).

### 4.6 Gemini 3 Pro

**Strengths:** Handles complex tasks that Flash can't. Good D&D rules knowledge. Scored 8/8 on T048 level-up validation (better than all OpenAI models on the original prompt).

**Weaknesses:** Expensive ($2/1M input, $12/1M output), slower (5-15s). Outputs JSON format instead of @-tag notation on T085 (functional but 14% more tokens).

**Best for:** Level-up validation (T048), location compression (T085), agentic compression (T084).

### 4.7 Temperature Compatibility Matrix

| Model | reasoning=none + temp | reasoning>none + temp | No reasoning + temp |
|---|---|---|---|
| gpt-4.1 | N/A | N/A | Yes |
| gpt-5.2 | Yes | No (stripped) | N/A |
| gpt-5.4 | Yes | No (stripped) | N/A |
| gpt-5.4-mini | Yes | No (stripped) | N/A |
| gpt-5-mini | N/A (none not supported) | No | N/A |
| Gemini (all) | N/A | N/A | Ignored (defaults to 1.0) |

---

## 5. Prompt Engineering Findings

### 5.1 Prompts Modified

15 game prompts were surgically modified to work with next-gen models. All changes are backwards-compatible with gpt-4.1.

| Callsite | Prompt | Changes | Root Cause |
|---|---|---|---|
| T017 | combat_compression_engine.py inline | PLAYER TURN rules, ROUND COMPLETE, @STATUS precedence | New models didn't handle partial turn processing |
| T040 | combat_validation_prompt_compressed.txt | VALIDATION_PHILOSOPHY, empty_actions_override, use_provided_data, tied initiative | gpt-5.2/5.4 over-reject valid combat responses |
| T035 | npc_builder.py inline | NAME HANDLING, EQUIPMENT REQUIREMENTS, RACIAL TRAITS | Gemini strips titles, produces sparse equipment |
| T054 | character_validator.py inline | Magical ammo exclusion, electrum handling, trade goods | All models fabricate or skip edge cases |
| T048 | leveling_validation_prompt.txt | HP math verification, omission tolerance, verdict discipline | Models miss CON modifier in HP math or over-reject valid level-ups |
| T085 | location_compressor.py inline | Anti-fabrication priority rules, @C dedup, @AREA/@DC/@HOOKS source restrictions, format example, EVT coverage | Gemini fabricates data, all models miss @AREA sub-rooms |
| T084 | ai_narrative_compressor_agentic.py inline | Numeric detail preservation, canon location reuse | Gemini drops HP/spell slot numbers, renames canon locations |
| T047 | level_up_system_prompt.txt (v3) | Greeting+HP combined, response format with actions:[], askQuestion ban, subclass HP bonuses, NPC auto-path | Models split greeting/HP into 2 turns, Gemini drops actions key, misses Draconic Resilience |
| T041 | combat_manager.py inline (v2) | No markdown, 150-250 word target, ASCII only | Gemini adds markdown headers, gpt-5.4-mini Unicode artifacts, gpt-5.2 too verbose |
| T032 | module_stitcher.py inline (v2) | ASCII only (no smart quotes) | Smart quotes in player-facing travel narration |
| T038 | campaign_manager.py inline (v2) | ASCII + no-markdown | Smart quotes and em-dashes in campaign saga output |
| T066 | main.py inline (v2) | ASCII + no-markdown (both copies) | Smart quotes + Gemini markdown headers in transition summaries |
| T016 | adv_summary.py inline (v2) | ASCII + no-markdown | Smart quotes in adventure chronicles |
| T018 | cumulative_summary.py inline (v2) | ASCII + no-markdown | Smart quotes in location summaries |
| T019 | cumulative_summary.py inline (v2) | ASCII + no-markdown | Smart quotes in expanded journal entries |
| T044/T045 | combat_sim_prompt_compressed.txt (V5) | preroll_weapon_mapping, @HOLDING scope/no_current_actor_skip, perspective_rule (2nd person), HARD_STOP, v_stop_boundary validator | Gemini-pro wrong preroll die, gpt-5.4 skipped actor turns, Gemini 3rd person narration, Gemini crossed turn boundaries |

### 5.2 Common Prompt Issues with Next-Gen Models

**The "no_assumptions" trap:** Prompts with strict "do not assume" rules cause gpt-5.2+ to reject valid derivations (e.g., calculating attack bonuses from ability scores). Fix: replace with "use_provided_data" that explicitly permits derivation.

**The "over-validation" pattern:** Validation prompts designed for gpt-4.1 (which under-validates) become hyper-strict with gpt-5.2+ (which over-validates). Fix: add "VERDICT DISCIPLINE" rules and "err toward valid" philosophy.

**The "fabrication" pattern:** Gemini models fill empty tables with invented data (spells, DCs, items) because the prompt says "tables MUST NOT be empty." Fix: add explicit "empty when source array absent" rule, distinguish inference (allowed for @HAZ) from fabrication (forbidden for @DC, @LOOT).

**The "format default" pattern:** Gemini defaults to JSON objects when the prompt expects custom token notation. Fix: add concrete output examples showing the exact expected format.

**The "canon drift" pattern:** Gemini paraphrases canonical names instead of reusing them exactly. Fix: add "EXACTLY as written" reuse rules.

**The "smart quotes" pattern:** All models (including gpt-4.1 baseline) produce Unicode smart quotes and em-dashes in narrative prose output. Windows cp1252 console crashes on these. Fix: add "Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode" to all narrative prompts. Standardized across 8 callsites.

**The "turn boundary violation" pattern (combat-specific):** Gemini-flash at medium/high thinking crosses initiative turn boundaries -- when told "STOP AT: [player]" it processes the player's turn anyway. Higher thinking made it WORSE (15/32 vs 17/32). Fix: add HARD_STOP rule and v_stop_boundary validator. gemini-pro respects boundaries; flash does not.

**The "preroll mapping" pattern (combat-specific):** Gemini-pro incorrectly maps preroll dice to weapons -- uses the Shortsword die for a Shortbow attack. Fix: add explicit `preroll_weapon_mapping` rule stating positional assignment (first die = first weapon).

**The "holding over-deferral" pattern (combat-specific):** gpt-5.4 correctly defers out-of-turn player actions but sometimes also skips the current actor's turn entirely. Fix: add `scope` and `no_current_actor_skip` to @HOLDING, clarifying that only the player's action is deferred -- current actor still acts normally.

### 5.3 The Iteration Loop

For each prompt issue:
1. Identify the failure from reviewer output or agent analysis
2. Make the minimal surgical change to the prompt
3. Retest all models (ensure the fix doesn't break what was working)
4. Verify backwards compatibility with gpt-4.1 baseline
5. Commit only after 2+ consistent runs

Average iterations per prompt: 3-4 (T040 took 6 iterations, T085 took 6).

---

## 6. Callsite Migration Detail

### 6.1 Completed Callsites (40)

| Task | Description | OpenAI Model | Gemini Model | Prompt Change | Key Finding |
|---|---|---|---|---|---|
| T013 | Transition narration | gpt-5-mini | gemini-3.1-flash-lite | No | Old CALLSITE_MODEL_MAP pattern |
| T067 | Main DM loop | gpt-5.2 none / gpt-5-mini low | gemini-3.1-pro low / gemini-3.1-flash-lite minimal | No | Dynamic full/mini routing |
| T065 | AI response validation | gpt-5.2 low | gemini-3-flash medium | No | gpt-5.2\|none = 0/15 correct |
| T082 | Action predictor | gpt-5-mini low | gemini-3-flash minimal | No | Speed critical, fires every turn |
| T079 | Character data updates | gpt-5-mini low | gemini-3.1-flash-lite minimal + response_schema | No | Gemini needs response_schema |
| T017 | Combat compression | gpt-5-mini low | gemini-3-flash low | **v5** | Plain text tags, response_format=None |
| T046 | Initiative tracker | gpt-5.2 none | gemini-3-flash minimal | No | gpt-5-mini DISQUALIFIED |
| T078 | Character effects | gpt-5.2 none | gemini-3-flash high | No | flash\|minimal fails Sneak Attack edge |
| T040 | Combat validation | gpt-5.4 none | gemini-3-flash low | **v4** | First gpt-5.4 callsite. 5.2 fails validation |
| T051 | Character validator (AC) | gpt-5.2 none | gemini-3-flash minimal | No | Easy callsite. 5.4-mini miscalculates |
| T034 | Monster builder | gpt-5.2 none | gemini-3-flash minimal | No | Creative gen, temp=0.7 |
| T035 | NPC builder | gpt-5.2 none | gemini-3-flash minimal | **v4** | Name handling, equipment, racial traits |
| T050 | Effects categorizer | gpt-5.2 none | gemini-3-flash low | No | Separate file from T051 |
| T052 | Inventory validator | gpt-5.2 none | gemini-3-flash minimal | No | Easy callsite |
| T053 | Batched validator | gpt-5.2 none | gemini-3-flash minimal | No | Combines T051+T052+T054 |
| T054 | Currency consolidation | gpt-5.2 none | gemini-3-flash low | **v3** | Magical ammo, electrum, trade goods |
| T081 | Encounter update | gpt-5.2 none | gemini-3-flash minimal | No | Easy, all models pass |
| T077 | Plot update | gpt-5.2 none | gemini-3-flash minimal | No | Easy, all models pass |
| T021 | Transition validation | gpt-5.2 none | gemini-3-flash minimal | No | Easy, all models pass |
| T048 | Level-up validation | gpt-5.2 none | gemini-3-pro low | **v4** | 8/8 perfect after prompt fix |
| T085 | Location compression | gpt-5.2 none | gemini-3-pro low | **v5** | Hardest callsite. Plain text @-tags. |
| T020 | Narrative compression | gpt-5.4-mini none | gemini-3-flash minimal | No | First gpt-5.4-mini callsite |
| T084 | Agentic EVT compression | gpt-5.4-mini none | gemini-3-pro low | **v3** | Numeric preservation, canon reuse |
| T048 | Level-up validation | gpt-5.2 none | gemini-3-pro low | **v4** | HP math verification, verdict discipline |
| T047 | Level-up conversation | gpt-5.2 none | gemini-3-flash low | **v3** | Interactive interview, temp=0.7. Greeting+HP combined. |
| T086 | NPC auto-level-up | gpt-5.2 none | gemini-3-flash low | No | Single-shot JSON, temp=0.3. Reuses LEVELUP_CONV configs. |
| T014 | NPC movement decision | gpt-5.4-mini none | gemini-3-flash minimal | No | Background NPC remove/update_status/move. 40/40 pass. |
| T091 | Monster reconciliation | gpt-5.4-mini none | gemini-3-flash minimal | No | Prunes killed/fled monsters. response_format=None. |
| T041 | Combat dialogue summary | gpt-5.4-mini none | gemini-3-flash low | **v2** | Narrative summary, temp=0.8. No markdown, ASCII, 150-250 words. |
| T030 | Narrative parsing | gpt-5.4-mini none | gemini-3-flash low | No | Parse narrative to module params. JSON output. |
| T032 | Travel narration | gpt-5.4-mini none | gemini-3-flash low | **v2** | ASCII rules added. JSON output. |
| T033 | Content safety | gpt-5.4-mini none | gemini-3-flash low | No | Family-friendly review. JSON output. |
| T038 | Campaign saga summary | gpt-5.4-mini none | gemini-3-flash low | **v2** | ASCII + no-markdown. response_format=None. |
| T066 | Transition summary | gpt-5.4-mini none | gemini-3-flash low | **v2** | ASCII + no-markdown. response_format=None. |
| T015 | Location JSON update | gpt-5.4-mini none | gemini-3-flash low | No | Location schema update. JSON output. |
| T016 | Adventure chronicle | gpt-5.4-mini none | gemini-3-flash low | **v2** | ASCII + no-markdown. response_format=None. |
| T018 | Location summary | gpt-5.4-mini none | gemini-3-flash low | **v2** | ASCII + no-markdown. response_format=None. |
| T019 | Expanded journal | gpt-5.4-mini none | gemini-3-flash low | **v2** | ASCII + no-markdown. response_format=None. |
| T043 | Combat resume | gpt-5.4 none | gemini-3-pro low | No | Re-engagement narration. Unified from partial branch. |
| T044 | Combat initial scene | gpt-5.4 none | gemini-3-pro low | **V5** | Scene setup + initiative. Floating temperature. |
| T045 | Combat per-turn | gpt-5.4 none | gemini-3-pro low | **V5** | Most complex callsite. 16-criteria audit. 5 prompt iterations. |
| T087 | NPC name canonicalization | gpt-5.4-mini none | gemini-3-flash minimal | No | Extract first name from D&D character names. temp=0.0. response_format=None. max_tokens removed. |
| T088 | NPC merge confirmation | gpt-5.4-mini none | gemini-3-flash minimal | No | Boolean same-entity check. temp=0.0. response_format=None. max_tokens removed. |
| T089 | Prompt sanitizer | gpt-5.4-mini none | gemini-3-flash minimal | No | DALL-E content policy cleanup. temp=0.3. response_format=None. |
| T090 | Quest formatter | gpt-5.4-mini none | gemini-3-flash minimal | **v2** | Quest journal formatting. temp=0.3. ASCII rule 9 added to prompt. |
| T094 | Bestiary promotion | gpt-5.4-mini none | gemini-3-flash minimal | **v2** | Monster manual-style description. temp=0.7. ASCII rule added. response_format=None. |
| T095 | NPC portrait prompts | gpt-5.4-mini none | gemini-3-flash minimal | **v2** | Image gen prompt for DALL-E. temp=0.8. ASCII rule added. response_format=None. |
| T083 | Bestiary updater | gpt-5.4-mini none | gemini-3-flash minimal | **v2** | Monster description JSON. temp=0.7. ASCII rule added. JSON mode kept. |
| T093 | AI starting location | gpt-5.4-mini none | gemini-3-flash minimal | **v2** | Starting location selection. temp=0.7. ASCII rule added. response_format=None (regex). |
| T042 | Combat round summary | gpt-5.4-mini none | gemini-3-flash minimal | **V2** | Critical: feeds back into combat history. V2 fixes death tracking. temp=0.1. JSON mode. Last DM_MINI_MODEL callsite. |
| T031 | Module field generation | gpt-5.2 none | gemini-3-pro low | **v2** | First DM_MAIN_MODEL. Generates module fields dynamically. temp=0.7. ASCII rule. response_format=None. |
| T036 | Plot field generation | gpt-5.2 none | gemini-3-pro low | **v2** | Plot field generation. temp=0.7. ASCII rule. response_format=None. |
| T037 | Plot structure generation | gpt-5.2 none | gemini-3-pro low | **v2** | Full plot structure + side quests. temp=0.8. JSON mode. ASCII rule. gpt-5.2 generates richest content. |
| T092 | Character creation | gpt-5.2 none | gemini-3-pro low | **v3** | Startup finalization hardening. Prompt now enforces confirmation -> JSON, requires top-level ammunition array, and blocks schema-metadata leakage. |
| T059 | NPC codex generator | gpt-5.2 none | gemini-3-pro low | No | Critical anti-hallucination. Full-tier for accuracy. temp=0.1. response_format=None. |
| T063 | Arrival narration | gpt-5.4-mini none | gemini-3-flash minimal | No | Module transition narration. Downgraded to mini-tier. temp=0.8. response_format=None. |
| T064 | Narrative stitching | gpt-5.4-mini none | gemini-3-flash minimal | No | Module transition stitching. Downgraded to mini-tier. temp=0.8. response_format=None. |
| T022 | Location name generation | gpt-5.2 none | gemini-3-pro low | **v2** | Thematic room names for areas. temp=0.8. ASCII rule. response_format=None. |
| T023 | Area name refinement | gpt-5.2 none | gemini-3-pro low | **v2** | Pipeline foundation — refined name feeds all downstream. temp=0.8. JSON mode. ASCII rule. |
| T024 | Area description | gpt-5.2 none | gemini-3-pro low | **v2** | Atmospheric area description. temp=0.8. ASCII rule. response_format=None. |
| T025 | Location field generation | gpt-5.2 none | gemini-3-pro low | **v2** | Single location field. Legacy/fallback (T026 replaced it). temp=0.7. ASCII rule. |
| T026 | Location batch generation | gpt-5.2 none | gemini-3-pro low | **v2** | HEAVIEST callsite. All locations in one shot, 21-field schema. temp=0.8. JSON mode. ASCII rule. |
| T027 | Location chronicle | gpt-5.4-mini none | gemini-3-flash low | No | Narrative chronicle compression. DM_SUMMARIZATION_MODEL. temp=0.6. response_format=None. |
| T028 | Plot unification | gpt-5.2 none | gemini-3-pro low | No | Global PP/SQ ID sequencing. JSON mode. temp=0.7. Critical for module integrity. |
| T029 | Plot hook enhancement | gpt-5.2 none | gemini-3-pro low | No | Enhances hooks with PP/SQ references. JSON mode. temp=0.6. |

### 6.2 Model Variable Completion

| Variable | Callsites | Status |
|---|---|---|
| CHARACTER_VALIDATOR_MODEL | T050-T054 (5) | **DONE** |
| NARRATIVE_COMPRESSION_MODEL | T017, T020, T084 (3) | **DONE** |
| DM_VALIDATION_MODEL | T040, T048, T065 (3) | **DONE** |
| DM_EFFECTS_MODEL | T078 (1) | **DONE** |
| NPC_BUILDER_MODEL | T035 (1) | **DONE** |
| MONSTER_BUILDER_MODEL | T034 (1) | **DONE** |
| ACTION_PREDICTION_MODEL | T082 (1) | **DONE** |
| PLAYER_INFO_UPDATE_MODEL | T079 (1) | **DONE** |
| LOCATION_COMPRESSION_MODEL | T085 (1) | **DONE** |
| ENCOUNTER_UPDATE_MODEL | T081 (1) | **DONE** |
| PLOT_UPDATE_MODEL | T077 (1) | **DONE** |
| TRANSITION_VALIDATOR_MODEL | T021 (1) | **DONE** |
| LEVEL_UP_MODEL | T047, T086 (2) | **DONE** |
| NPC_INFO_UPDATE_MODEL | T014, T091 (2) | **DONE** |
| COMBAT_DIALOGUE_SUMMARY_MODEL | T041 (1) | **DONE** |
| DM_SUMMARIZATION_MODEL | T030, T032, T033, T038, T066 (5) | **DONE** |
| ADVENTURE_SUMMARY_MODEL | T015, T016, T018, T019 (4) | **DONE** |
| COMBAT_MAIN_MODEL | T043, T044, T045 (3) | **DONE** |
| DM_MINI_MODEL | T042, T083, T087-T090, T093-T095 (9) | **DONE** |
| DM_MAIN_MODEL | T022-T029, T031, T036-T037, T059, T063-T064, T092 (15) | **DONE** |

### 6.3 Migration Complete

**ALL RUNTIME CALLSITES MIGRATED.** 64/64 complete (100%). All 21 model variables fully migrated.

Every callsite now routes through `api_client.create_completion()` with per-provider model configs. The legacy `gpt-4.1` path remains as a fallback on every callsite via the `else: # legacy` branch.

---

## 7. Cost and Performance Analysis

### 7.1 Model Pricing (from reference docs)

| Model | Input ($/1M) | Output ($/1M) | Notes |
|---|---|---|---|
| gpt-4.1 | ~$2.00 | ~$8.00 | Being sunset |
| gpt-5.2 | $2.00 | $10.00 | Primary OpenAI |
| gpt-5.4 | $2.50 | $15.00 | 40% more than 5.2 |
| gpt-5.4-mini | ~$0.40 | ~$1.60 | Mini pricing (est.) |
| gpt-5-mini | ~$0.30 | ~$1.20 | Mini pricing (est.) |
| gemini-3-flash | $0.50 | $3.00 | Free tier available |
| gemini-3-pro | $2.00 | $12.00 | No free tier |

### 7.2 Latency Ranges by Callsite Type

| Type | Baseline (4.1) | Best OpenAI | Best Gemini |
|---|---|---|---|
| Simple JSON (T081, T077) | 1-2s | 1-2s (5.2\|none) | 1-2s (flash\|minimal) |
| Validation (T040, T048) | 1-3s | 2-5s (5.4\|none / 5.2\|none) | 2-8s (flash\|low / pro\|low) |
| Creative generation (T034, T035) | 5-30s | 5-35s (5.2\|none) | 8-12s (flash\|minimal) |
| Compression (T085, T084) | 5-15s | 20-35s (5.2\|none) | 8-40s (pro\|low) |
| Narrative (T020) | 5-7s | 2-4s (5.4-mini\|none) | 2-3s (flash\|minimal) |
| Module generation (T026 batch) | 15-20s | 50-75s (5.2\|none) | 20-25s (pro\|low) |
| Plot unification (T028) | 5-7s | 8-10s (5.2\|none) | 10-12s (pro\|low) |
| Mini utilities (T087-T090) | 0.5-1s | 1-2s (5.4-mini\|none) | 0.7-1s (flash\|minimal) |

### 7.3 Gemini Cost Advantage

For callsites where gemini-flash works, the cost savings are significant:
- T046 initiative tracker: $0.0026 vs $0.0087 (70% cheaper)
- T082 action predictor: ~$0.001 vs ~$0.003 (67% cheaper)
- T081 encounter update: ~$0.001 vs ~$0.002 (50% cheaper)

For callsites requiring gemini-pro, costs are similar to OpenAI.

---

## 8. Lessons Learned

### 8.1 Technical Lessons

1. **Never trust the reviewer blindly.** The GPT-5.4 reviewer is excellent for comparative quality scoring but can be wrong about ground truth (T040). Always verify with independent agents on validation callsites.

2. **Temperature compatibility is a hard constraint.** gpt-5-mini doesn't support temperature at any reasoning level. gpt-5.4-mini does. This single difference makes 5.4-mini viable for many callsites where 5-mini isn't.

3. **More reasoning often hurts.** On T046, T078, T084, and others, higher reasoning levels (low, medium) scored worse than none. The models over-think and find problems that don't exist.

4. **Gemini defaults to JSON.** Even with `response_format=None`, Gemini's natural output format for structured data is JSON objects. For custom notation formats (@-tags, EVT blocks), explicit format examples are essential.

5. **Prompt changes are sometimes necessary.** The "prompts are frozen" rule was too absolute. 15 prompts needed targeted modifications for next-gen model compatibility. All changes were backwards-compatible and additive (no existing rules removed).

6. **Combat is the hardest callsite.** T045 required 5 prompt iterations and a 16-criteria quality audit with blind agent reviews to achieve 100% pass rates. The combat prompt is 500+ lines of compressed rules -- even small ambiguities cause different models to diverge on turn boundaries, preroll usage, and initiative compliance.

7. **gpt-5.2 hallucinated game state in combat.** It invented a full 10-creature initiative order labeled as "authoritative" that wasn't in the input. This is a disqualifying failure for any callsite where the model's plan text could influence downstream game state parsing. gpt-5.4 never exhibited this behavior.

8. **Gemini-flash fails at complex instruction following.** Flash models at medium/high thinking cross turn boundaries despite explicit STOP instructions. Higher thinking made the violations WORSE. gemini-pro with low thinking correctly respects boundaries. Flash is viable for simple JSON tasks but not for combat.

### 8.2 Process Lessons

1. **Full input data matters.** Early T085 tests truncated inputs at 6K chars. Models appeared to "fabricate" data that was actually just missing from their input. Always test with complete inputs.

2. **Blind agent review catches systematic bias.** The GPT-5.4 reviewer has preferences (favors verbose output, penalizes format looseness). Independent agents with fresh eyes catch cases where the reviewer's standards don't match gameplay reality.

3. **One model does not fit all.** The 24 migrated callsites use 5 different OpenAI models and 3 different Gemini models across varying reasoning/thinking levels. Cookie-cutter replacement would have failed.

4. **The deep merge parser matters.** On T054, we discovered the game's `deep_merge_dict()` function handles partial currency updates correctly. What looked like a "missing silver/copper" bug was actually the parser working as designed.

5. **Iterate in small cycles.** The most effective prompt improvements came from: identify one specific failure -> make one surgical change -> retest -> verify no regression. Batch changes often caused regressions.

### 8.3 Session 2 Lessons (DM_MINI + DM_MAIN completion)

6. **ASCII rule standardization works.** Adding "Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols" to every creative/narrative prompt eliminated Unicode issues across all models. This is a one-line, model-agnostic, backwards-compatible fix.

7. **Full-tier vs mini-tier is a deliberate design choice.** Module transition narration (T063/T064) was downgraded from DM_MAIN_MODEL to mini-tier because it's just prose. NPC codex generation (T059) stayed full-tier because it feeds the anti-hallucination system. The model tier should match the accuracy requirement, not the legacy variable name.

8. **Config parameter name collisions are real.** `area_generator.py` has a method parameter called `config` (type `AreaConfig`) that shadowed `import config`. Fixed with `import config as app_config`. Always check for parameter collisions when adding module-level imports.

9. **Module generation pipeline is sequential.** T023 output (area name) feeds T022 (location names) which feeds T026 (location batch). Synthetic tests should chain outputs to validate the pipeline end-to-end, not just test callsites in isolation.

10. **Death tracking in combat summaries requires explicit prompting.** T042's original prompt said "creatures that died this round" but round state includes pre-existing deaths at 0 HP. Models (especially Gemini) missed these. V2 prompt with "ALL creatures at 0 HP regardless of when they died" fixed it across all models.

11. **Stale code accumulates.** Found dead register_callsite for T068 (no corresponding capture_and_fanout), orphaned OpenAI imports, unused model variable imports (DM_VALIDATION_MODEL, COMBAT_DIALOGUE_SUMMARY_MODEL). Clean up dead code during migration, not after.

12. **Gemini-pro cost is negligible for module generation.** At $2/$12 per 1M tokens, a full module build with 15+ API calls costs roughly $0.10-0.50 total. The quality difference between flash and pro matters more than the cost difference for one-time generation tasks.

---

## 9. Reproducibility

### 9.1 Synthetic Test Scripts

All synthetic test scripts are in `tests/model_validation/`:

| Script | Callsite | What it tests |
|---|---|---|
| test_t065_gpt52_reasoning.py | T065 | gpt-5.2 reasoning levels |
| test_t065_gemini_thinking.py | T065 | Gemini thinking levels |
| test_t065_live_validation.py | T065 | Full replay all entries |
| test_t079_gemini_schema.py | T079 | Gemini response_schema |
| test_t017_compression.py | T017 | Plain text compression |
| test_t046_initiative.py | T046 | Initiative tracking |
| test_t040_combat_validation.py | T040 | Combat validation (v4 prompt) |
| test_t047_levelup_conversation.py | T047 | Level-up interview (4 scenarios) |
| test_t047_extended.py | T047 | 8 extended scenarios (Warlock, Sorcerer, Paladin, etc.) |
| test_t014_t091_npc_updates.py | T014/T091 | NPC movement + monster reconciliation |
| test_t041_combat_dialogue_summary.py | T041 | Combat narrative summary (5 scenarios) |
| test_t030_t032_t033_t038_t066_summarization.py | T030-T066 | DM summarization batch (8 scenarios) |
| test_t015_t016_t018_t019_adventure_summary.py | T015-T019 | Adventure summary batch (4 scenarios) |
| test_t044_combat_initial.py | T044 | Combat initial scene (5 complexity levels) |
| test_t045_combat_turn.py | T045 | Combat per-turn (simplified format) |
| test_t045_combat_turn_v2.py | T045 | Production-accurate format (real combat log data) |
| test_t087_t088_t089_t090_mini_utilities.py | T087-T090 | DM_MINI utility callsites (name canon, merge, sanitize, quest fmt) |
| test_t094_t095_web_creative.py | T094/T095 | Web interface creative generation (bestiary, NPC portraits) |
| test_t083_t093_mini_medium.py | T083/T093 | Bestiary updater + AI starting location |
| test_t042_combat_round_summary.py | T042 | Combat round summary with death tracking (V2 prompt) |
| test_t031_module_field_generation.py | T031 | Module field generation (first DM_MAIN callsite) |
| test_t036_t037_plot_generation.py | T036/T037 | Plot field + structure generation |
| test_t092_character_creation.py | T092 | Character creation conversational AI |
| test_t059_npc_codex_detailed.py | T059 | NPC codex extraction (anti-hallucination, detailed accuracy) |
| test_t063_t064_narration_mini.py | T063/T064 | Narration mini-tier comparison (full vs mini models) |
| test_t059_t063_t064_dm_main.py | T059/T063/T064 | Combined DM_MAIN callsite test |
| test_t023_area_name_refinement.py | T023 | Area name refinement (pipeline foundation) |
| test_t022_location_names.py | T022 | Location name generation (uses T023 output as context) |
| test_t026_location_batch.py | T026 | Location batch generation (21-field schema compliance) |
| test_t027_t028_t029_final.py | T027-T029 | Chronicle + plot unification + hook enhancement |

### 9.2 Capture Data

Model captures are in `model_captures/`:
- `T0XX.json` -- real gameplay captures (from play sessions)
- `T0XX_synthetic.json` -- synthetic test captures
- `T0XX_v2.json` / `T0XX_v3.json` -- prompt iteration captures

### 9.3 Review Tool

`tools/capture_quality_reviewer.py` -- sends prompt + outputs to GPT-5.4 for qualitative scoring. Usage:
```bash
python tools/capture_quality_reviewer.py T067 --entry 0 --reviewer gpt
```

---

## 10. Completed: Web UI Provider Selector

The web UI provider selector was completed on April 5, 2026. Implementation details:

### 10.1 UI Changes (game_interface.html)

```html
<div class="settings-section">
    <div class="settings-section-title">AI Provider</div>
    <div class="settings-item">
        <label for="model-provider-select">Provider</label>
        <select class="settings-select" id="model-provider-select"
                title="Each AI task uses a model selected specifically for that task type based on quality testing">
            <option value="legacy">Legacy (GPT-4.1) - Stable baseline</option>
            <option value="openai">OpenAI (GPT-5.x) - Next-gen, tested per task</option>
            <option value="gemini">Gemini 3.1 - Alternative provider, tested per task</option>
            <option value="lmstudio">LM Studio (Local) - Zero API cost</option>
        </select>
        <div class="settings-help">
            Models are selected per-task based on quality testing.
            Legacy is recommended for stability.
        </div>
    </div>
</div>
```

### 10.2 Backend Changes (web_interface.py)

- `get_model_provider` SocketIO handler -- returns current provider for UI sync on page load
- `set_model_provider` SocketIO handler -- updates MODEL_PROVIDER and persists to user_settings.json
- Provider choice survives server restarts via `persist_provider()` / `load_persisted_provider()`

### 10.3 Capture System Updates (model_config.py + multi_model_capture.py)

- `TASK_CAPTURE_CONFIGS` dict (70 entries) -- maps task_id to (OpenAI config name, Gemini config name)
- `get_capture_variants_for_task()` -- returns per-callsite capture variants instead of tier-based
- 3-tier variant lookup: task_overrides → per-callsite configs → tier-based fallback

### 10.4 Configuration Updates (config_template.py)

```python
# OPENAI_API_KEY (Required): Used for Legacy (GPT-4.1) and OpenAI (GPT-5.x) providers
# Get your key at: https://platform.openai.com/api-keys
OPENAI_API_KEY = "your_openai_api_key_here"

# GEMINI_API_KEY (Optional): Used for Gemini 3.1 provider
# Only needed if you want to use Gemini as an alternative AI provider
# Get your key at: https://aistudio.google.com/apikey
GEMINI_API_KEY = "your_gemini_api_key_here"
```

### 10.5 Startup Character-Creation Stabilization (T092)

After live debugging in April 2026, startup was additionally hardened around character finalization:

- **Root cause found:** startup occasionally saved character JSON without top-level `ammunition`, then `update_character_data` hit `KeyError: 'ammunition'` during startup-to-main handoff context build.
- **Prompt path refactor:** startup prompt construction was centralized into `utils/startup_prompt_builder.py`, and `utils/startup_wizard.py` now calls this shared builder.
- **Synthetic harness correction:** the T092 synthetic replay harness originally replayed captured system prompts (stale), which produced misleading iteration results. Harness now supports:
  - `exact_capture` mode (for reproduction)
  - `current_prompt` mode (for validating current live prompt revisions)
- **Validation evidence:** corrected `current_prompt` reliability runs reached **15/15** pass on the Smashing Jack confirmation replay (`Yes, this loosk good`) across Legacy/OpenAI/Gemini matrix attempts.
- **Repo artifacts added for repeatability:**
  - `tests/test_startup_wizard_prompt_reliability.py`
  - `tests/synthetic_data/startup_wizard_t092_smashing_jack_case.json`
  - `utils/startup_prompt_builder.py`

### 10.6 Startup Regression Hotfix (April 9, 2026)

After T092 stabilization, a critical race condition was discovered in the startup-to-main handoff that caused the game UI to remain stuck on "starting game" with no DM/player messages displayed.

**Root Causes:**

1. **Race condition in message flush logic:** `web_interface.py` line 270 checked `startup_ready_pending` flag BEFORE the marker handler at line 333 had a chance to set it. This created a timing window where the DM content queue would flush with no listeners waiting.

2. **Multiple `game_started` emission points:** Four separate locations emitted `game_started` events (startup handoff, marker handler, DM section check, fallback). Timing-dependent race meant the first emitter could fire before listeners registered in the frontend.

3. **Empty input polling loop:** `startup_wizard.py` contained an infinite polling loop `while not get_input():` that could hang indefinitely in web mode where input comes from SocketIO events, not stdin.

**Implementation Fix:**

1. **Removed `startup_ready_pending` intermediate state entirely** -- it was the source of the race condition. The startup process now commits directly to the terminal state without intermediate polling.

2. **Consolidated `game_started` emission to single point:** Marker handler (`startup_kickoff_done`) is now the sole authoritative emitter. All other emission points were removed.

3. **Removed `in_dm_section` check from DM content flush** -- the marker is the single source of truth for startup completion, not arbitrary DM section detection.

4. **Removed empty input polling loop** -- replaced with direct event processing in web mode.

5. **Kept prompt detection fallback** -- if marker somehow gets lost (catastrophic failure path), the system still detects `"generation_status": "GENERATION_COMPLETE"` in the AI response and falls back to emitting `game_started` with debug logging.

**Verification:**

- All 22 startup tests pass (`tests/test_startup*.py`)
- Integration test specifically validates single-emit behavior: `tests/test_startup_game_started_emission.py` (`test_game_started_does_not_double_emit`)
- Manual smoke test: game UI transitions immediately from "starting" to playable state with DM/player messages visible

**Impact:**

This fix eliminated the final blocking issue for startup handoff. Combined with T092's ammunition validation and prompt refactoring, the startup system is now stable across all provider configurations (Legacy/OpenAI/Gemini).

### 10.7 Legacy Character Auto-Repair (April 10, 2026)

**Issue:** Players updating their game code could experience crashes from legacy character files missing required fields (e.g., `ammunition`).

**Root cause:** The `normalize_for_runtime()` repair function in `conversation_utils.py` only repairs character data in-memory for API calls. The actual character files on disk were never updated.

**Fix:**
1. Added `repair_and_persist_character()` function to `character_sheet_contract.py`
2. Added startup repair step in `main.py` that runs after party tracker is loaded
3. Repairs both party members and party NPCs
4. Only writes to disk if changes were made (no unnecessary file churn)

**Fields repaired:** 30+ potential missing fields including:
- Arrays: ammunition, equipment, feats, classFeatures, racialTraits, etc.
- Objects: abilities, spellcasting, currency, proficiencies, senses, etc.
- Scalars: level, hitPoints, armorClass, status, condition, etc.

**Verification:** Tests in `tests/test_legacy_character_repair.py`

---

## 11. Next Steps (Post-UI Completion)

Remaining work:

1. **Live gameplay validation** -- play full game sessions on each provider. Priority: combat (T043-T045), level-up (T047), module generation (T022-T028), and character creation (T092).
2. **Cost monitoring** -- track per-session API costs across providers. Compare provider costs in real gameplay.
3. **Gemini temperature limitation** -- `_gemini_completion` ignores temperature. Combat retry escalation (temperature reduction) has no effect on Gemini path. Consider adding thinking_level escalation for Gemini retries.
4. **Merge to main** -- after gameplay validation, merge `multi-model-refactor` branch to main.

## 12. Module Generation Pipeline

The module generation toolkit (T022-T029, T031, T036-T037) is a sequential pipeline where each callsite's output feeds the next. Understanding this pipeline was critical for model selection and testing.

### 12.1 Pipeline Sequence

```
T031 (module_generator.py) — Module metadata: name, description, worldMap, mainPlot
  ↓
T023 (area_generator.py) — Area name refinement: broadens concepts into regional names
  ↓
T022 (area_generator.py) — Location names: thematic room names using area context
  ↓
T026 (location_generator.py) — Location batch: ALL locations for area in one shot (21 fields each)
  ↓
T036/T037 (plot_generator.py) — Plot generation: per-area plots with side quests
  ↓
T028 (module_builder.py) — Plot unification: combines area plots, global PP/SQ numbering
  ↓
T029 (module_builder.py) — Plot hooks: enhances location hooks with PP/SQ references
  ↓
T027 (location_summarizer.py) — Chronicle: compresses transition records into narrative
```

### 12.2 Critical Dependencies

- **T023 is the foundation** — the refined area name is used by ALL downstream callsites
- **T026 is the heaviest** — generates complete location objects with 21 required fields and 9 required door subfields
- **T028 has strict ID sequencing** — plot point IDs must be PP001-PPnnn, side quest IDs must be SQ001-SQnnn GLOBALLY (not restarting per plot point)
- **T025 is legacy** — T026 (batch) replaced it, but T025 was migrated for completeness

### 12.3 Schema Compliance Findings

T026 (location batch) uses `response_format={"type": "json_object"}` for API-enforced JSON validity. However, schema compliance (all 21 fields present, correct door structure, valid dangerLevel enum) depends on the prompt explicitly listing field requirements. All models produced schema-compliant output when the required fields were clearly stated in the prompt.

### 12.4 Testing Strategy

Synthetic tests for the pipeline used **chained outputs** — T023's gpt-5.2|none output became T022's input context, and T022's output became T026's location stub names. This validates the pipeline end-to-end, not just individual callsites.

---

## 13. Combat Quality Audit Framework

The combat migration (T043/T044/T045) required the most rigorous testing of any callsite batch. A 16-criteria quality audit was developed:

1. Turn window compliance (process ONLY instructed actors)
2. Sacred Flame / out-of-turn action handling (defer, acknowledge, do not resolve)
3. Correct preroll die usage (positional weapon mapping)
4. Hit/miss math transparency (full calculation shown)
5. Damage calculation (correct generic pool die + bonus)
6. Target selection logic (HP-based tactical priority)
7. Action routing (enemy->updateEncounter, ally->updateCharacterInfo)
8. combat_round value correctness
9. Narration perspective (2nd person for player)
10. Narration quality (vivid, cinematic, sensory per @NARRATION_STYLE)
11. Plan transparency (math, routing, stop reason)
12. No hallucinated data (no invented initiative orders or stats)
13. ASCII compliance
14. Skeleton attack count (1 attack, no Multiattack)
15. JSON schema completeness
16. Turn boundary respect (HARD STOP when instructed)

Each criterion scored 0-2 (max 32 points). Models were tested with 2 blind runs each for stability assessment. gpt-5.4|none and gemini-pro|low both achieved 100% (32/32) after V5 prompt iteration. This framework is reusable for future combat-related model evaluations.

---

## 14. Live Gameplay Regression Fixes (2026-04-10)

First live gameplay session on the `multi-model-refactor` branch revealed two critical regressions.

### 14.1 Startup Resume: Blank Screen

**Symptom:** Game starts, web UI shows "Game Running", but no DM narration displayed. Player sees blank screen until they type something.

**Root cause chain:**
1. The startup lease system (`startup_state.json`) persists `status: "kickoff_done"` across game sessions
2. No code path resets this state between sessions -- `sync_wizard_completion()` only transitions `"none"` -> `"wizard_complete"`, not `"kickoff_done"` -> anything
3. On restart, `claim_kickoff_lease()` sees `"kickoff_done"` -> returns `"already_done"` -> `_run_startup_kickoff_once()` returns early at line 261 WITHOUT calling `process_ai_response()`
4. The "player has returned" injection generates an AI response and saves it to history, but passes it as `precomputed_response` to the kickoff, which discards it without processing
5. A previous "CRITICAL FIX" at lines 3189-3219 only handled the edge case where `was_injected=False` (no user messages) -- the normal resume case (`was_injected=True`) was not covered

**Fix:** Call `issue_new_attempt_id()` at the top of `main_game_loop()` to reset lease state per session. Removed the band-aid CRITICAL FIX block. Added safety net fallback for precomputed responses if kickoff fails for other reasons.

**Secondary fix:** DM narration during startup was typed as `'startup'` (plain text rendering) instead of `'narration'` (full DM styling with avatar/header). Changed `_flush_dm_buffer()` to always type DM content as `'narration'`.

**Commits:** `9c6a8ee`, `4f8d67a`

**Note:** This bug was NOT introduced by the multi-model migration. It existed in the startup hardening work (commit `93ef590`) that predated callsite migration. The lease system was designed for exactly-once kickoff semantics but lacked a session reset.

### 14.2 T079: NameError Silently Breaks All Character Updates

**Symptom:** DM narrates gold transfer (player gives 5 gold to NPC), but neither character's gold changes. No error visible to player.

**Root cause:** The T079 migration (commit `4964dd1`) removed `get_model_for_character()` and the line `model = get_model_for_character(character_role)`. But line 1503 in `update_character_info.py` still referenced the undefined `model` variable in a debug logging dict:

```python
"model_used": model,  # NameError after migration deleted get_model_for_character()
```

The crash occurred AFTER the API call succeeded (correct delta computed) but BEFORE `deep_merge_dict()` and `safe_write_json()`. The generic `except Exception` handler caught the `NameError`, retried 3 times (burning API credits), then returned `False`. The concurrent executor in `main.py` silently ignored `False` returns.

**Impact scope:** ALL character updates on ALL providers -- gold, inventory, HP, conditions, equipment. Every `updateCharacterInfo` action from the DM was silently dropped since the T079 migration.

**Fix:** `"model_used": model` -> `"model_used": char_update_config["model"]`

**Commit:** `0000d6f`

### 14.3 Lessons for Future Migrations

1. **Grep for deleted names.** After removing any function or variable, grep the entire file for remaining references. The T079 `NameError` would have been caught instantly by `grep -n "model" update_character_info.py` after deleting `get_model_for_character()`.

2. **Capture testing has a blind spot.** Capture tests validate model output quality, not the surrounding Python code. A `NameError` in debug logging between the API call and the merge/save step is invisible to capture testing. End-to-end gameplay testing is the only way to catch plumbing bugs.

3. **Silent failure patterns are dangerous.** The combination of `except Exception` -> retry -> return `False` -> caller ignores `False` created a triple-layered silence. Each layer individually is reasonable; together they make bugs invisible. Consider: (a) logging the exception type in the retry handler, (b) raising on unexpected exception types (NameError is never a transient failure), (c) having the caller warn when character updates return False.

4. **Validate agents' conclusions.** The first round of subagents dispatched to investigate the startup bug concluded all resume scenarios "work correctly" -- but never traced HOW the narration actually reaches the screen after the kickoff is skipped. Always verify that an agent's conclusion follows from its evidence, not just from its confidence.
