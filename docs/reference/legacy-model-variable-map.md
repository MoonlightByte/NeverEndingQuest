# Legacy Model Variable Map

**Date:** 2026-03-19
**Status:** Agent-validated (2 rounds), manually verified
**Purpose:** Documents how the 21 model config variables map to actual model strings in the legacy (gpt-4.1) system. This is the baseline for designing per-provider model selection.

---

## Model Variables -> Legacy Model Strings

### Full Tier (11 variables -> gpt-4.1-2025-04-14)

| Model Variable | Legacy Model | Callsite Count | Task IDs | Primary Usage |
|---|---|---|---|---|
| DM_MAIN_MODEL | gpt-4.1-2025-04-14 | 17 | ~~T013~~(DONE),T022-T028,T031,T036,T037,~~T046~~(DONE),T059,T063,T064,T092 | Main DM narration, transitions, generators, stitching |
| DM_FULL_MODEL | gpt-4.1-2025-04-14 | 0 dedicated | (used dynamically by ~~T067~~(DONE) via selected_model) | Complex actions requiring JSON operations |
| DM_VALIDATION_MODEL | gpt-4.1-2025-04-14 | 3 | ~~T040~~(DONE),~~T048~~(DONE),~~T065~~(DONE) | AI response validation, combat validation |
| COMBAT_MAIN_MODEL | gpt-4.1-2025-04-14 | 3 | T043,T044,T045 | Primary combat loop (T045 uses dynamic assignment) |
| CHARACTER_VALIDATOR_MODEL | gpt-4.1-2025-04-14 | 5 (active) | ~~T050~~(DONE),~~T051~~(DONE),~~T052~~(DONE),~~T053~~(DONE),~~T054~~(DONE) | Character sheet validation (+4 in backup: T055-T058) |
| NPC_BUILDER_MODEL | gpt-4.1-2025-04-14 | 1 | ~~T035~~(DONE) | NPC generation |
| MONSTER_BUILDER_MODEL | gpt-4.1-2025-04-14 | 1 | ~~T034~~(DONE) | Monster generation |
| LEVEL_UP_MODEL | gpt-4.1-2025-04-14 | 2 | T047,T086 | Level up conversation + validation |
| ACTION_PREDICTION_MODEL | gpt-4.1-2025-04-14 | 1 | ~~T082~~(DONE) | Predicting player action types |
| LOCATION_COMPRESSION_MODEL | gpt-4.1-2025-04-14 | 1 | ~~T085~~(DONE) | Location data compression |
| DM_EFFECTS_MODEL | gpt-4.1-2025-04-14 | 1 | ~~T078~~(DONE) | Character effect tracking |

### Mini Tier (10 variables -> gpt-4.1-mini-2025-04-14)

| Model Variable | Legacy Model | Callsite Count | Task IDs | Primary Usage |
|---|---|---|---|---|
| DM_MINI_MODEL | gpt-4.1-mini-2025-04-14 | 10 | T042,T043,T083,T087,T088,T089,T090,T093,T094,T095 | Simple conversations, combat fallback, utilities, web UI |
| DM_SUMMARIZATION_MODEL | gpt-4.1-mini-2025-04-14 | 5 | T030,T032,T033,T038,T066 | Module stitching, campaign export, response summarization |
| NARRATIVE_COMPRESSION_MODEL | gpt-4.1-mini-2025-04-14 | 3 | ~~T017~~(DONE),~~T020~~(DONE),~~T084~~(DONE) | Narrative/combat/incremental compression |
| COMBAT_DIALOGUE_SUMMARY_MODEL | gpt-4.1-mini-2025-04-14 | 1 | T041 | Combat dialogue summarization |
| ADVENTURE_SUMMARY_MODEL | gpt-4.1-mini-2025-04-14 | 4 | T015,T016,T018,T019 | Adventure summary, cumulative summary |
| PLOT_UPDATE_MODEL | gpt-4.1-mini-2025-04-14 | 1 | ~~T077~~(DONE) | Plot state updates |
| PLAYER_INFO_UPDATE_MODEL | gpt-4.1-mini-2025-04-14 | 1 | ~~T079~~(DONE) | Player character data updates (dynamic selection) |
| NPC_INFO_UPDATE_MODEL | gpt-4.1-mini-2025-04-14 | 2 | T014,T091 | NPC data updates, location state reconciliation |
| ENCOUNTER_UPDATE_MODEL | gpt-4.1-mini-2025-04-14 | 1 | ~~T081~~(DONE) | Encounter data updates |
| TRANSITION_VALIDATOR_MODEL | gpt-4.1-mini-2025-04-14 | 1 | ~~T021~~(DONE) | Location transition validation |

---

## Summary

- **21 model variables** across the codebase (11 full, 10 mini)
- **2 actual model strings** in legacy: `gpt-4.1-2025-04-14` (full) and `gpt-4.1-mini-2025-04-14` (mini)
- **11 full-tier variables** -> 35 runtime callsites (+ T067 which dynamically selects DM_FULL_MODEL or DM_MINI_MODEL)
- **10 mini-tier variables** -> 29 runtime callsites
- Total: ~64 runtime callsites using `capture_and_fanout`

## Known Issues Found During Validation

1. **BUG: T039** (`campaign_manager.py:564`) references `config.DM_SUMMARY_MODEL` which **does not exist** in `model_config.py`. Should be `config.DM_SUMMARIZATION_MODEL`. Will crash if this code path executes.
2. **T045** uses dynamic variable `combat_model` assigned at runtime, not a direct config reference
3. **T067** dynamically selects between `DM_FULL_MODEL` and `DM_MINI_MODEL` based on action prediction -- not a fixed model variable
4. **T079** uses dynamic `get_model_for_character()` which resolves to PLAYER_INFO_UPDATE_MODEL or NPC_INFO_UPDATE_MODEL
5. **T020** uses `self.COMPRESSION_MODEL` set from `config.NARRATIVE_COMPRESSION_MODEL` in `__init__`
6. **T049** (`storage_processor.py:286`) uses `self.model` set from `config.DM_MAIN_MODEL` in `__init__` -- not directly visible in grep for model variable names

## Design Implication

The variable names provide per-callsite granularity that collapses to just 2 models in legacy. The new provider system needs to let each variable resolve to a *different* model per provider, enabling decisions like:
- T013 uses `DM_MAIN_MODEL` (full/gpt-4.1 in legacy) but should use mini (gpt-5-mini) when openai is selected
- Each variable can independently map to full or mini per provider based on capture testing results

This is what `CALLSITE_MODEL_MAP` in `model_config.py` will address.
