# OpenAI Model Migration: GPT-4.1 to GPT-5.2

## Summary

Migrate all 36+ OpenAI API call sites from GPT-4.1/GPT-4.1-mini to GPT-5.2/GPT-5-mini. Stay on the Chat Completions API. Preserve old code commented out for future Gemini/local model use. Validate via synthetic testing with AI reviewer agents.

## Constraints

- **DO NOT modify prompts** -- only change model names, parameters, and code logic
- **Preserve old 4.1 code** -- comment out with `# LEGACY_4.1:` markers, do not delete
- **Stay on Chat Completions API** -- do not migrate to Responses API
- **400K context window** -- down from 1M with GPT-4.1; verify all call sites fit
- **Tune DOWN reasoning** -- for full model replacements, test lowest reasoning_effort that maintains quality
- **Combat is highest priority** -- it is the hardest task; start complex, throttle down
- **Speed matters** -- balance failure rates against latency

## Model Mapping

| Current Model | New Model | Default Reasoning | Notes |
|---|---|---|---|
| `gpt-4.1-2025-04-14` | `gpt-5.2` | `none` | Per OpenAI guide: gpt-4.1 -> gpt-5.2 with none reasoning |
| `gpt-4.1-mini-2025-04-14` | `gpt-5-mini` | varies | Prompt tuning via parameter adjustment only |
| `gpt-5-2025-08-07` (existing) | `gpt-5.2` | mapped from existing | Existing GPT-5 code becomes reference |
| `gpt-5-mini-2025-08-07` (existing) | `gpt-5-mini` | mapped from existing | Already partially implemented |

### Combat Exception

Combat starts at `reasoning=medium` or `high` and throttles down. The existing GPT-5 partial implementation in `combat_manager.py` already demonstrates this pattern with `GPT5_USE_HIGH_REASONING_ON_RETRY`.

### Parameter Compatibility (GPT-5.2)

- `temperature`, `top_p`, `logprobs` -- **only work with reasoning=none**
- `reasoning_effort` -- `none` (default), `low`, `medium`, `high`, `xhigh`
- `verbosity` -- `low`, `medium` (default), `high` (new parameter, controls output length)
- When escalating from reasoning=none to low/medium/high, temperature must be dropped

## API Call Site Inventory (36+ sites)

### Tier 1: Combat (Highest Risk)
| File | Model Variable | Current Model | New Model | Notes |
|---|---|---|---|---|
| `core/managers/combat_manager.py` | `COMBAT_MAIN_MODEL` | gpt-4.1 | gpt-5.2 | 8+ API calls, retry logic with temp escalation, GPT-5 partial impl exists |
| `core/ai/combat_compression_engine.py` | `NARRATIVE_COMPRESSION_MODEL` | gpt-4.1-mini | gpt-5-mini | Combat context compression |

### Tier 2: Main DM (High Risk)
| File | Model Variable | Current Model | New Model | Notes |
|---|---|---|---|---|
| `core/ai/action_handler.py` | `DM_MINI_MODEL`, `DM_MAIN_MODEL` | gpt-4.1/mini | gpt-5.2/5-mini | Location transitions, NPC updates, action processing |
| `main.py` | `DM_MAIN_MODEL`, `DM_SUMMARIZATION_MODEL`, `DM_VALIDATION_MODEL` | gpt-4.1 | gpt-5.2 | Terminal game loop |
| `web/web_interface.py` | `DM_MINI_MODEL` | gpt-4.1-mini | gpt-5-mini | Web chat responses |
| `utils/startup_wizard.py` | `DM_MAIN_MODEL`, `DM_MINI_MODEL` | gpt-4.1/mini | gpt-5.2/5-mini | Character creation |
| `utils/action_predictor.py` | `ACTION_PREDICTION_MODEL` | gpt-4.1 | gpt-5.2 | Intelligent routing predictions |

### Tier 3: Validation (Medium Risk)
| File | Model Variable | Current Model | New Model | Notes |
|---|---|---|---|---|
| `core/validation/character_validator.py` | `CHARACTER_VALIDATOR_MODEL` | gpt-4.1 | gpt-5.2 | AC, inventory, currency validation; temp 0.1; caching |
| `core/validation/character_effects_validator.py` | `CHARACTER_VALIDATOR_MODEL` | gpt-4.1 | gpt-5.2 | Effects validation; temp 0.1 |
| `core/ai/transition_validator.py` | `TRANSITION_VALIDATOR_MODEL` | gpt-4.1-mini | gpt-5-mini | Transition validation; temp 0.3 |
| `core/validation/npc_codex_generator.py` | `DM_MAIN_MODEL` | gpt-4.1 | gpt-5.2 | NPC name extraction |

### Tier 4: Generation (Context Window Risk)
| File | Model Variable | Current Model | New Model | Notes |
|---|---|---|---|---|
| `core/generators/module_generator.py` | `DM_MAIN_MODEL` | gpt-4.1 | gpt-5.2 | Module generation -- VERIFY 400K LIMIT |
| `core/generators/area_generator.py` | `DM_MAIN_MODEL` | gpt-4.1 | gpt-5.2 | Area generation; 3 API calls |
| `core/generators/location_generator.py` | `DM_MAIN_MODEL` | gpt-4.1 | gpt-5.2 | Location generation |
| `core/generators/location_summarizer.py` | `self.ai_model` | configurable | gpt-5.2 | Location summaries |
| `core/generators/plot_generator.py` | unknown | gpt-4.1 | gpt-5.2 | Plot generation |
| `core/generators/npc_builder.py` | `NPC_BUILDER_MODEL` | gpt-4.1 | gpt-5.2 | AI NPC creation |
| `core/generators/monster_builder.py` | `MONSTER_BUILDER_MODEL` | gpt-4.1 | gpt-5.2 | Monster creation with CR context |
| `core/generators/module_stitcher.py` | `DM_SUMMARIZATION_MODEL` | gpt-4.1-mini | gpt-5-mini | Module stitching, safety review |

### Tier 5: Updates & Compression (Lower Risk)
| File | Model Variable | Current Model | New Model | Notes |
|---|---|---|---|---|
| `updates/update_character_info.py` | `PLAYER_INFO_UPDATE_MODEL` | gpt-4.1-mini | gpt-5-mini | Character sheet updates; retry loop |
| `updates/update_character_effects.py` | `DM_EFFECTS_MODEL` | gpt-4.1 | gpt-5.2 | Effects updates; temp 0.3 |
| `updates/plot_update.py` | `PLOT_UPDATE_MODEL` | gpt-4.1-mini | gpt-5-mini | Plot progression |
| `updates/update_encounter.py` | `ENCOUNTER_UPDATE_MODEL` | gpt-4.1-mini | gpt-5-mini | Encounter state |
| `core/ai/incremental_compression.py` | hardcoded mini | gpt-4.1-mini | gpt-5-mini | Conversation compression |
| `utils/compression/ai_narrative_compressor_agentic.py` | `NARRATIVE_COMPRESSION_MODEL` | gpt-4.1-mini | gpt-5-mini | EVT notation compression |
| `utils/compression/location_compressor.py` | `LOCATION_COMPRESSION_MODEL` | gpt-4.1 | gpt-5.2 | Location encounter compression |
| `core/ai/adv_summary.py` | `ADVENTURE_SUMMARY_MODEL` | gpt-4.1-mini | gpt-5-mini | Adventure summaries; temp 0.8 |
| `core/ai/cumulative_summary.py` | `ADVENTURE_SUMMARY_MODEL` | gpt-4.1-mini | gpt-5-mini | Long-term memory |
| `core/managers/campaign_manager.py` | `DM_SUMMARIZATION_MODEL` | gpt-4.1-mini | gpt-5-mini | Module summaries |
| `utils/level_up.py` | `LEVEL_UP_MODEL` | gpt-4.1 | gpt-5.2 | Level-up guidance; temp 0.3 |
| `utils/npc_name_canonicalizer.py` | `DM_MINI_MODEL` | gpt-4.1-mini | gpt-5-mini | Name extraction |
| `utils/npc_reconciler.py` | `DM_MINI_MODEL` | gpt-4.1-mini | gpt-5-mini | NPC matching; temp 0.0; max_tokens=1 |
| `utils/quest_player_formatter.py` | `DM_MINI_MODEL` | gpt-4.1-mini | gpt-5-mini | Quest formatting |
| `utils/prompt_sanitizer.py` | `DM_MINI_MODEL` | gpt-4.1-mini | gpt-5-mini | Prompt cleaning |
| `utils/bestiary_updater.py` | `DM_MINI_MODEL` | gpt-4.1-mini | gpt-5-mini | Monster descriptions |

## Synthetic Testing Framework

### Approach
For each call site, build a synthetic test that:
1. Uses real input data from existing game files (conversation histories, combat logs, character sheets)
2. Sends the same input to GPT-5.2 (or 5-mini) with varying reasoning_effort levels
3. An AI reviewer agent evaluates output against:
   - JSON structure compliance (matches schema the code expects)
   - Game mechanic accuracy (HP, AC, damage calculations)
   - Behavioral parity with GPT-4.1
   - Speed/latency metrics

### Test Volume
- 30-50 API calls per tier
- 5 tiers = 150-250 total test calls
- Each full-model call site tested at reasoning levels: none, low, medium, high
- Pick the lowest reasoning level that passes all quality checks

### Test Data Sources
- `modules/conversation_history/conversation_history.json` (166KB, ~41K tokens)
- `combat_logs/` (8.7MB across 154 files)
- `characters/eirik_hearthwise.json` (33KB, main character)
- `modules/*/areas/*.json` (445 location files)
- `modules/campaign_archives/` (3.6MB of historical context)
- `data/bestiary/monster_compendium.json` (194KB)
- `data/bestiary/npc_compendium.json` (64KB)

### Context Window Verification
- GPT-4.1: 1,000,000 tokens
- GPT-5.2: 400,000 tokens
- Current estimated usage per request: 70,000-100,000 tokens (well within 400K)
- **Risk area**: Module generation may use more context; verify during Phase 4
- Compression pipeline (70-90% reduction) provides significant headroom

## Implementation Phases

### Phase 1: Setup & Audit
- Create `OpenAI` branch off main
- Document all 36+ API call sites with current configuration
- Map each call site to new model + initial reasoning_effort
- Identify all existing GPT-5 partial implementations
- Verify context window usage for generation tasks against 400K limit

### Phase 2: model_config.py Update
- Add GPT-5.2 model constants
- Comment out GPT-4.1 constants with `# LEGACY_4.1:` markers
- Add `REASONING_EFFORT_*` constants per task type
- Add `VERBOSITY_*` settings where applicable
- Keep backward-compatible toggle mechanism

### Phase 3: Code Migration (per call site, by tier)
For each call site:
- Comment out old 4.1 call structure with `# LEGACY_4.1:` prefix
- Wire in new 5.2 model with appropriate reasoning_effort
- Handle parameter compatibility (temperature only with reasoning=none)
- Preserve existing retry/fallback logic
- Update escalation to use reasoning_effort where appropriate
- Use existing GPT-5 combat implementation as reference pattern

### Phase 4: Synthetic Testing
- Build test harness using existing game data files
- Run 30-50 API calls per tier (5 tiers)
- AI reviewer agents evaluate output quality and JSON compliance
- Tune reasoning_effort DOWN for each full-model call site
- Document results: pass/fail, speed, reasoning level chosen
- Fix any failing call sites

### Phase 5: Review & Finalize
- Side-by-side comparison report (4.1 vs 5.2 per call site)
- Final validation pass across all tiers
- Update model_config.py with winning configurations
- Document final model assignments and reasoning levels

## Risk Mitigation

- **Combat failures**: Start at high reasoning, only tune down after confirmed working
- **Context overflow**: Compression pipeline already reduces 70-90%; verify generation tasks specifically
- **JSON compliance**: AI reviewer agents validate every output against expected schemas
- **Speed regression**: Track latency per call site; reasoning=none should be faster than 4.1
- **Preserved rollback**: All old code commented out, can revert per call site
