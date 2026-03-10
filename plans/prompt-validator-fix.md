# Prompt and Validator Fix Plan

## Executive Summary

This plan hardens the Narrator DM prompt, validation pipeline, and character-update path so the system becomes:

- clearer about what the LLM is allowed to decide,
- stricter about what Python alone owns as mechanical truth,
- faster on common turns,
- more reliable for 5e mechanics,
- more coherent across narration, validation, and state updates.

The central problem is not a lack of rules text. The central problem is contract drift and too much mechanics-by-prose. The current stack has good foundations, but several layers disagree about action contracts, and the most sensitive mechanics still pass through freeform natural-language interpretation after validation.

This plan fixes that in stages, starting with low-risk contract alignment and then moving toward structured mechanics.

## Status

- Status: Planning only
- Priority: High
- Scope: Narrator prompt, validator prompt, main validation pipeline, and mechanical update path
- Risk: Medium to High if attempted as one large patch
- Recommended rollout: incremental, phase-gated

## Core Goals

1. Make Python the unambiguous source of truth for mechanics.
2. Reduce prompt and validator contradictions.
3. Shrink the amount of LLM interpretation required for mechanical updates.
4. Preserve narrative freedom, scene flavor, and NPC voice.
5. Reduce end-to-end latency for standard turns.
6. Improve 5e compliance for rests, spell slots, saving throws, concentration, HP, conditions, and sheet updates.

## Non-Goals

- Do not remove narrative richness or theatrical narration.
- Do not replace the full DM with a fully deterministic state machine.
- Do not rewrite the entire combat system as part of this change.
- Do not break backward compatibility for existing single-player and tabletop workflows in one pass.

## Current Pain Points

### 1. Contract Drift Between Layers

The following contracts are visibly out of sync:

- `rest`
  - Narrator prompt says emit `rest` and let Python auto-restore.
  - Runtime does this already.
  - Compressed validator still expects `updateCharacterInfo`-style rest recovery.

- save/restore actions
  - Validator parameter expectations do not match action handler expectations.

- module creation
  - Validator still assumes a stale `createNewModule` parameter shape.

### 2. Mechanics Still Flow Through Prose

`updateCharacterInfo` currently looks structured at the narrator level, but the actual `changes` payload is still freeform English interpreted by another AI layer. That creates a second hallucination surface after the narrator already passed validation.

### 3. Validation Is Heavy and Uneven

- Main generation call
- validation call
- possible retries
- possible `updateCharacterInfo` AI pass per touched character
- possible post-write validators

This is accurate but expensive. The validator also gets stronger inventory context than live mechanical context in many cases.

### 4. Truth Is Split Across Too Many Representations

Current truth sources include:

- DM Note
- current system prompt
- current validation prompt
- conversation history
- campaign chronicle/location chronicle
- updater prompt
- post-write character validators

The architecture says DM Note is authoritative for dynamic state, but some other injected context still carries overlapping dynamic information.

### 5. 5e Coverage Is Inconsistent

The prompt references many 5e mechanics correctly, but not all of them are represented as a deterministic action contract or deterministic runtime check.

Most exposed areas:

- rests,
- spell slots,
- concentration,
- death saves,
- saving throws,
- condition synchronization,
- class feature usage,
- HP change legality.

## Desired End State

The final system should work like this:

1. The narrator decides intent, framing, mood, and dramatic presentation.
2. The narrator chooses from a small, explicit action grammar.
3. Deterministic Python prechecks reject impossible or contradictory state mutations.
4. Validator only reviews the parts that are still semantically risky.
5. Python applies common mechanics directly from structured payloads.
6. The AI updater remains only as a fallback for genuinely fuzzy sheet edits.

In short:

- LLM owns flavor and choice interpretation.
- Python owns reality.

## Design Principles

### Principle 1: One Canonical Action Contract

There must be exactly one authoritative contract for narrator actions and parameters. Prompts, validators, and runtime must all derive from or mirror that same contract.

### Principle 2: Deterministic First, LLM Second

If a mechanic can be validated or applied deterministically, do that before or instead of asking an LLM to infer it.

### Principle 3: Structured Mechanics, Freeform Narrative

Narration should remain freeform. Mechanics should become increasingly structured.

### Principle 4: Validator Should Be Targeted

Do not send the full semantic world to the validator for every turn. Validate only the risks relevant to the current response.

### Principle 5: Backward-Compatible Migration

Introduce new structured paths first, keep legacy prose paths behind compatibility shims, then tighten enforcement after regression coverage is in place.

## Proposed Workstreams

## Workstream A - Contract Alignment

### Objective

Remove prompt/runtime drift so the narrator prompt, validation prompt, and action handler describe the same system.

### Files

- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/system_prompt.txt`
- `prompts/validation/validation_prompt.txt`
- `core/ai/action_handler.py`

### Changes

1. Align `rest` action across all prompt layers.
   - Validator must explicitly accept `rest` as the primary contract.
   - Remove stale guidance saying short/long rest must directly emit `updateCharacterInfo`.
   - Preserve `updateTime` requirement in same bundle.

2. Align save/restore/delete-save parameter shapes with runtime.
   - Update prompt docs to match actual `action_handler` behavior.
   - If runtime contract is wrong or outdated, fix runtime and prompt together in one pass.

3. Align `createNewModule` parameter expectations.
   - Decide whether the contract is narrative-first or explicit-parameter-first.
   - Reflect the same decision in system prompt, validator prompt, and runtime parser.

4. Add a prompt contract audit checklist.
   - Action name present in prompt
   - Parameter shape present in prompt
   - Validation prompt accepts same action and parameter shape
   - Runtime handles same shape

### Deliverables

- zero known contract mismatches for currently supported actions,
- regression tests that fail if prompt and runtime drift on action names/params.

## Workstream B - Prompt Simplification and Logical Reordering

### Objective

Make the main narrator prompt easier for the model to follow by separating hard rules from creative guidance.

### Files

- `prompts/system_prompt_compressed.txt`
- `prompts/system_prompt.txt`

### Changes

Reorder prompt into five strict tiers:

1. Output contract
2. Truth hierarchy
3. turn-resolution policy
4. mechanic-specific rules
5. narrative style and flavor guidance

### Proposed Prompt Order

1. `@FMT` and `@OUTPUT_CONSTRAINTS`
2. `@STATE_SYNC`
3. `@ACTIONS` and `@PARAMS`
4. `@RESOLUTION_LADDER` (new)
5. `@COMBAT`, `@TIME`, `@REST`, `@SPELLS`, `@HEALING`, `@SKILL_CHECKS`, `@TRAPS`
6. NPC and travel rules
7. multi-PC guidance
8. narrative flavor blocks

### New `@RESOLUTION_LADDER` Block

Introduce one explicit decision ladder for each player turn:

- If action is purely descriptive and changes nothing -> narration only
- If action may fail and player roll is required -> ask for roll, no outcome yet
- If NPC/enemy/system roll is required -> narrator resolves it
- If state changes -> emit structured action(s)
- If commitment point is reached -> emit `createEncounter`

This should reduce ambiguity around checks, saves, traps, healing, and inventory actions.

### Deliverables

- slimmer compressed prompt,
- clearer priority ordering,
- fewer overlapping rules stated in multiple places.

## Workstream C - Structured Mechanics for High-Risk Updates

### Objective

Move common mechanics away from freeform `changes` prose and toward structured action payloads.

### Files

- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `core/ai/action_handler.py`
- `updates/update_character_info.py`

### Phase C1: Add Structured Payload Support Without Breaking Legacy

Allow `updateCharacterInfo.parameters` to accept either:

- legacy: `{"characterName": str, "changes": str}`
- structured: `{"characterName": str, "changes": str, "ops": [...]}`

Where `ops` is a list of explicit operations.

### Initial `ops` Types

- `hp_delta`
- `set_hp`
- `spell_slot_delta`
- `condition_add`
- `condition_remove`
- `inventory_add`
- `inventory_remove`
- `currency_delta`
- `xp_delta`
- `feature_use`
- `feature_restore`
- `temp_effect_add`
- `temp_effect_remove`

### Phase C2: Deterministic Application for Supported `ops`

Inside `action_handler`, if `ops` is present:

- validate each op deterministically,
- apply directly in Python,
- bypass the freeform AI interpretation path where possible.

### Phase C3: Keep Freeform AI Path as Fallback Only

If `ops` is absent or unsupported:

- keep legacy `changes` path,
- log fallback usage,
- progressively reduce its use over time.

### Deliverables

- common mechanics no longer depend on a second LLM pass,
- lower hallucination risk,
- lower per-turn latency for sheet changes.

## Workstream D - Deterministic Guards for 5e Mechanics

### Objective

Add deterministic enforcement for the mechanics most likely to desync.

### Files

- `core/ai/action_handler.py`
- `updates/update_character_info.py`
- new utility modules under `utils/` or `core/validation/`

### Guard Set D1: HP and Condition Integrity

- HP cannot go below 0
- healing cannot exceed max HP
- HP > 0 cannot coexist with unconscious state
- HP == 0 implies unconscious unless dead/stable rules explicitly say otherwise

### Guard Set D2: Spell Slot Integrity

- slots cannot underflow
- cantrips cannot consume slots
- leveled spells must consume legal slot unless a rule-based exception exists
- long rest restores valid slots
- short rest restores only rule-allowed resources

### Guard Set D3: Rest Integrity

- short rest minimum time
- long rest minimum time
- distinguish natural-language overnight rest from exact-duration rest
- preserve no-auto-Hit-Dice tracking policy unless project later adds it explicitly

### Guard Set D4: Saving Throw and Concentration Integrity

- explicit concentration save helper logic
- deterministic DC rule: max(10, half damage)
- deterministic save metadata in actions or combat flow
- death-save progression remains Python-side where possible

### Guard Set D5: Inventory and Currency Integrity

- no use of items not possessed
- transfer math validated before write
- ammunition spend always decrements legal ammo

### Deliverables

- clearer failure reasons,
- fewer impossible state writes,
- stronger 5e compliance without adding more prompt bulk.

## Workstream E - Validation Pipeline Refactor

### Objective

Reduce validation latency while making validation more truthful and more targeted.

### Files

- `main.py`
- `prompts/validation/validation_prompt_compressed.txt`
- possible new validation helpers under `utils/` or `core/validation/`

### Phase E1: Validation Mode Routing

Split validation into focused modes:

- `action_contract`
- `travel_transition`
- `npc_arrival_sync`
- `resource_and_inventory`
- `combat_initiation`
- `narrative_continuity`

Not every turn needs every mode.

### Phase E2: Deterministic-First Validation

Before LLM validation:

- JSON shape
- known action names
- parameter contract
- rest legality
- slot underflow
- HP bounds
- impossible inventory operations

If deterministic checks pass and the turn is low-risk, allow an LLM validator skip path.

### Phase E3: Better Validation Context

For each touched character, send a compact mechanical truth pack to validator:

- HP/max HP
- conditions
- spell slots
- death saves
- class feature usage
- inventory summary only if relevant

This should replace the current inventory-heavy but mechanically uneven validation context.

### Phase E4: Performance Controls

- stop compressing validation context unless token/size threshold exceeded
- reuse already loaded location/module data in one pass
- add timeout and escalating status updates for main validation path

### Deliverables

- fewer validator false negatives,
- lower latency,
- less duplicated context assembly.

## Workstream F - DM Note and Context Authority Cleanup

### Objective

Reduce overlapping dynamic-state sources so the LLM sees one current truth for mechanics.

### Files

- `utils/multi_pc_dm_note.py`
- `core/ai/conversation_utils.py`
- `core/ai/character_sheet_compressor.py`

### Changes

1. Keep DM Note as the only dynamic truth source for:
   - HP
   - conditions
   - spell slots
   - temp effects
   - current combat state

2. Trim overlapping dynamic values from injected system character summaries where practical.

3. Preserve static reference data in character summaries:
   - class
   - race
   - abilities
   - proficiencies
   - known spells
   - attacks
   - backstory/personality

4. Ensure validator and generation both consume the same mechanical truth format for touched characters.

### Deliverables

- less stale-state conflict,
- clearer model priority ordering,
- better narrative continuity grounded in live reality.

## Workstream G - Saving Throws as First-Class Contract

### Objective

Make saving throws explicit and robust instead of implied in prose.

### Options

#### Option G1 - Minimal

Keep save resolution in narration, but add a deterministic save-resolution helper and better validation rules.

#### Option G2 - Preferred

Introduce a first-class action or structured sub-contract for save requests/results, such as:

- `requestRoll` for player-facing saves/checks
- deterministic metadata including roll type, DC, modifier source, target, and consequence

This can remain lightweight and need not become a full dice engine rewrite.

### Deliverables

- clearer save/check flow,
- cleaner concentration and trap handling,
- more reliable player roll prompts.

## Rollout Plan

### Phase 0 - Safety Prep

- add regression coverage around current behavior before changing contracts
- snapshot prompt contract assumptions in tests

### Phase 1 - Contract Sync

- fix prompt/validator/runtime drift
- no architectural changes yet

### Phase 2 - Validation and Performance Cleanup

- targeted validator modes
- deterministic prechecks
- timeout/status improvements

### Phase 3 - Structured Mechanics Introduction

- add `ops` support alongside legacy prose
- apply direct Python updates for supported ops

### Phase 4 - Authority Cleanup

- simplify dynamic context sources
- reduce stale duplicated state

### Phase 5 - Tightening and Deprecation

- measure fallback usage for legacy prose updates
- migrate common narrator examples to structured mechanics
- eventually require structured mechanics for high-risk updates

## Testing Strategy

## Contract Tests

- action names in prompt match runtime constants
- parameter shapes in prompt match action handler expectations
- validator accepts every supported action shape

## Deterministic Mechanics Tests

- HP damage/healing bounds
- spell slot spend/restore legality
- short/long rest outcomes by class
- concentration save DC logic
- death save progression
- ammunition decrement and item possession checks

## Validation Loop Tests

- low-risk turn can skip heavy validator when deterministic checks pass
- deterministic failures remain fail-closed
- validator malformed JSON does not silently greenlight unsafe mechanical updates

## Continuity Tests

- DM Note overrides stale narrative memory
- compressed conversation and validator share consistent truth for touched characters

## Performance Tests

Measure before/after on:

- narration-only turn
- narration + one inventory update
- travel turn
- rest turn
- multi-PC healing turn

Metrics:

- total model calls
- wall-clock latency
- average validator prompt size
- fallback frequency to legacy prose updater

## Success Criteria

The plan is successful when all of the following are true:

1. No known action contract mismatches remain between prompt, validator, and runtime.
2. `rest` flow is fully consistent across narrator, validator, and Python behavior.
3. Common HP/slot/inventory/condition updates no longer require freeform AI interpretation.
4. Main-turn latency drops measurably on low-risk and single-update turns.
5. Validator false failures on compliant turns are reduced.
6. Saving throws, concentration, and death-adjacent mechanics are clearer and more deterministic.
7. Narrative quality remains intact in gameplay testing.

## Recommended Implementation Order

If this is executed as a practical build sequence, use this order:

1. Contract sync for `rest`, save/restore, and module creation
2. validation-mode routing and deterministic prechecks
3. timeout/status hardening on main narrator/validator path
4. structured `updateCharacterInfo.ops` support
5. direct Python application for HP, slots, inventory, currency, conditions
6. DM Note / character-summary authority cleanup
7. saving-throw first-class contract

## Recommended First Build Slice

The safest first implementation slice is:

- fix `rest` contract drift,
- add action-contract parity tests,
- add deterministic slot/HP/inventory validation for touched characters,
- stop compressing validator context unless a threshold is exceeded.

That slice should provide immediate clarity and latency improvement without forcing a full structured-mechanics migration in one pass.

## Appendix A - Compressed Prompt Authority and Performance Addendum

This appendix records the post-audit follow-on work required after the initial contract-alignment and deterministic-precheck slices were implemented.

### A1. Canonical Prompt Loader

#### Objective

Make compressed prompts the live runtime authority for narrator and validator flows.

#### Rationale

The current codebase still loads `prompts/system_prompt.txt` in live narrator paths even though compressed prompts are the maintained source of truth. That leaves stale guidance active at runtime and keeps the narrator prompt much heavier than necessary.

#### Required Changes

- Add one shared loader for narrator and validator prompt selection.
- Make compressed prompts canonical for live runtime:
  - narrator -> `prompts/system_prompt_compressed.txt`
  - validator -> `prompts/validation/validation_prompt_compressed.txt`
- Keep uncompressed prompts as reference artifacts only, or generate them later if still needed for debugging/docs.
- Update:
  - `main.py`
  - `core/ai/conversation_utils.py`

#### Expected Impact

- Major static narrator prompt reduction.
- Eliminate live stale-rule drift between compressed and uncompressed prompt variants.
- Simplify future prompt maintenance by establishing one true runtime source.

### A2. Thresholded Validation Compression

#### Objective

Only compress validator context when the assembled payload is large enough to justify the extra work.

#### Required Changes

- Replace unconditional validation compression with threshold-based routing.
- Define size thresholds in bytes and/or estimated tokens.
- Keep fail-open fallback to current uncompressed validation flow if compression fails.

#### Expected Impact

- Lower wall-clock latency on common small/medium turns.
- Reduce unnecessary file I/O and compression overhead.
- Preserve long-context safety for big turns.

### A3. Validation Mode Routing and Skip Path

#### Objective

Route low-risk turns through deterministic validation only and reserve the LLM validator for semantically risky cases.

#### Proposed Validation Modes

- `action_contract`
- `travel_transition`
- `npc_arrival_sync`
- `resource_and_inventory`
- `combat_initiation`
- `narrative_continuity`

#### Required Changes

- Add deterministic risk classification before the validator call.
- Skip the LLM validator when:
  - JSON structure is valid,
  - actions are known and contract-valid,
  - deterministic guards pass,
  - and the turn does not touch high-risk narrative/state-sync categories.

#### Expected Impact

- Fewer validation calls on low-risk turns.
- Lower token spend and faster response times.
- Cleaner separation between deterministic mechanics and semantic judgment.

### A4. Prompt Reorder and Slimming

#### Objective

Make the compressed narrator prompt easier for the model to follow while preserving creativity and world tone.

#### Recommended Order

1. Output contract
2. Truth hierarchy
3. Action grammar
4. Resolution ladder
5. Mechanics rules
6. NPC/travel/multi-PC rules
7. Narrative style and flavor guidance

#### Required Changes

- Add `@RESOLUTION_LADDER` as proposed in the main plan.
- Remove duplicated or stale rule text.
- Move bulky examples and historical notes out of the live prompt where practical.

#### Expected Impact

- Better instruction salience.
- Less conflict between hard rules and flavor guidance.
- Improved creative response quality under tighter reality constraints.

### A5. Structured Mechanics Pilot (`ops`)

#### Objective

Begin migration away from prose-only `updateCharacterInfo.changes` for high-risk mechanics.

#### Initial `ops` Set

- `set_hp`
- `hp_delta`
- `spell_slot_delta`
- `inventory_add`
- `inventory_remove`
- `currency_delta`
- `condition_add`
- `condition_remove`

#### Required Changes

- Extend `updateCharacterInfo.parameters` to optionally include `ops`.
- Apply supported ops directly in Python.
- Keep prose `changes` as fallback only.

#### Expected Impact

- Lower hallucination surface.
- Less dependence on second-pass freeform AI interpretation.
- Stronger mechanics integrity with less prompt bulk.

### A6. Mechanical Truth Pack for Validator

#### Objective

Replace uneven validator context assembly with compact touched-character mechanical truth.

#### Required Payload

For each touched character, send only the relevant current-state snapshot:

- HP/max HP
- conditions
- spell slots
- death saves
- class feature usage
- inventory only when the turn references it

#### Expected Impact

- Fewer validator false failures.
- Lower validation prompt size.
- Better grounding in live state.

### A7. First-Class Save and Concentration Contract

#### Objective

Make saving throws and concentration logic explicit instead of inferred from prose.

#### Required Changes

- Add a lightweight save/check contract such as `requestRoll` or equivalent structured metadata.
- Add deterministic concentration DC helper logic: `max(10, half damage)`.
- Keep player-facing narration freeform.

#### Expected Impact

- Cleaner 5e save/check flow.
- Better concentration and trap handling.
- Clearer separation between player-facing prompts and state application.

### A8. Expanded Deterministic Guard Set

#### Objective

Extend deterministic mechanics coverage only after telemetry confirms low false-positive rates from the current guard set.

#### Candidate Extensions

- cantrip/no-slot legality
- slot underflow from explicit spend language
- unconscious vs HP contradiction
- ammo decrement legality beyond explicit removal wording
- rest duration legality at validator-precheck layer

#### Expected Impact

- Stronger reality constraints with minimal additional prompt weight.

## Updated Recommended Order After Audit

1. Canonical compressed prompt loader
2. Thresholded validation compression
3. Validation mode routing and low-risk skip path
4. Prompt reorder and slimming
5. Structured `ops` pilot
6. Mechanical truth pack for validator
7. First-class save/concentration contract
8. Expanded deterministic guards
