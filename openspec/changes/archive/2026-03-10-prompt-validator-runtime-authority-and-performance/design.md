## Context

After the first prompt-validator hardening slices, the most important remaining mismatch is source authority: compressed prompts are maintained as the real contract, but the live narrator path still loads `system_prompt.txt`. At the same time, validator performance still suffers from always-on compression and unconditional LLM validation on many low-risk turns.

This change addresses those bottlenecks without yet introducing structured mechanics or a save/check contract rewrite.

## Goals / Non-Goals

**Goals:**
- Make compressed prompts canonical at runtime.
- Avoid unnecessary validation compression on small turns.
- Skip LLM validation for low-risk deterministic-safe turns.
- Improve compressed narrator prompt order so rule salience is stronger and creativity is less buried by duplicated mechanics text.

**Non-Goals:**
- No `updateCharacterInfo.ops` support in this change.
- No save/check first-class action contract in this change.
- No full DM Note authority cleanup in this change.
- No combat prompt migration work in this change.

## Decisions

### Decision 1: Compressed prompt files are canonical runtime authority

**Decision:** Live narrator and validator paths SHALL load compressed prompt variants for runtime behavior.

**Rationale:** This matches actual maintained prompt ownership and removes stale drift from the live path.

### Decision 2: Validation compression becomes threshold-based

**Decision:** Validation context compression SHALL only run when the assembled payload exceeds a configured size threshold.

**Rationale:** Compression has value on large contexts but adds avoidable overhead on small turns.

### Decision 3: Deterministic low-risk turns may skip LLM validation

**Decision:** A turn MAY skip the LLM validator only if all of the following are true:
- JSON structure is valid
- action names and parameter shapes are known/acceptable
- deterministic mechanics precheck passes
- no covered high-risk categories are present

**Initial high-risk categories:**
- `createEncounter`
- `transitionLocation`
- `updatePartyTracker`
- `moveBackgroundNPC`
- `updatePartyNPCs`
- `createNewModule`
- any deterministic precheck failure

**Initial low-risk candidates:**
- narration-only turns
- simple `updateTime`
- simple `saveGame` / `listSaves`
- bounded `updateCharacterInfo` turns that pass deterministic prechecks and do not touch high-risk semantics

### Decision 4: Prompt reordering happens in the compressed narrator prompt only

**Decision:** This phase SHALL reorder and slim `system_prompt_compressed.txt` rather than trying to keep an equivalent uncompressed live prompt in sync.

**Rationale:** Once compressed runtime authority is established, prompt-quality work should target the live prompt directly.

### Decision 5: Use a simple resolution ladder for salience

**Decision:** Add a compact `@RESOLUTION_LADDER` block to the compressed narrator prompt.

**Required ladder states:**
- narration only if no state changes
- ask for roll if player-facing uncertainty exists
- narrator resolves NPC/system rolls when appropriate
- emit structured action(s) when state changes
- emit `createEncounter` at combat commitment point

## Risks and Mitigations

- **Risk:** Runtime switching to compressed prompt changes behavior unexpectedly.
  - **Mitigation:** Add source-contract tests and keep edits to loader paths isolated.
- **Risk:** Low-risk skip path may allow a turn through that should have been validated semantically.
  - **Mitigation:** Start with conservative high-risk routing and narrow skip eligibility.
- **Risk:** Prompt slimming may remove useful guardrails.
  - **Mitigation:** Reorder first, delete duplicates second, and keep regression tests focused on critical contract blocks.

## Migration Plan

### Phase 1 - Runtime Prompt Authority
- Switch narrator runtime loader to compressed prompt.
- Switch conversation-history prompt identity comparison to compressed prompt.
- Add source-contract tests.

### Phase 2 - Thresholded Validation Compression
- Add size-threshold routing for validation compression.
- Add tests for threshold behavior.

### Phase 3 - Low-Risk Validation Skip
- Add conservative routing helper for validation mode / skip decision.
- Skip LLM validator only for explicitly low-risk deterministic-safe turns.
- Add source and behavior tests.

### Phase 4 - Compressed Prompt Reorder
- Add `@RESOLUTION_LADDER`.
- Reorder compressed prompt so hard rules precede flavor guidance.
- Remove stale or duplicated compressed prompt guidance where safe.

## Deferred Follow-Ups

- Compact mechanical truth pack for touched characters.
- Structured `ops` support.
- First-class save/check contract.
- Expanded deterministic guard coverage after telemetry.
