# Parlay Hostile Resolution Loop Breaker

## Status

- Planned
- Priority: High (adventure progression blocker)
- Scope: Runtime state + prompt/validator contract alignment

## Should this be OpenSpec-driven?

Yes. This change crosses multiple layers (prompt contract, validator contract, runtime DM-note generation, and regression tests) and fixes a player-blocking loop. It should be tracked as a small OpenSpec change so implementation remains scoped and testable.

## Problem Summary

At `V04` (`Petitioner's Rest`), players can successfully parlay with Bloodshadow, but travel can still loop back into the same hostile blocker.

Observed causes:

1. Static module monster at V04 (`Bloodshadow`) remains present by design.
2. Runtime DM-note injects unconditional threat pressure (`Monsters should be active threats per engagement rules.`).
3. Resolution marker is not consistently persisted and/or consumed as authoritative state.
4. Prompt + validation contracts are not fully aligned around `updatePartyTracker` payloads for resolved hostile markers.

## Objective

After successful non-combat guardian appeasement at a location, the system should treat that specific hostile as resolved for travel and narration unless the party re-provokes it.

## Scope

### In Scope

- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`
- `utils/multi_pc_dm_note.py`
- `main.py`
- `scripts/test_parlay_travel_unblock.py` and/or targeted new test file

### Out of Scope

- Module JSON topology edits
- Combat engine refactor
- New action type creation

## Technical Plan

### Phase 1 - Contract Alignment

1. Extend `updatePartyTracker` parameter contract to explicitly allow:
   - `resolvedHostilesByLocation` (top-level dict)
   - nested `worldConditions` dict containing `resolvedHostilesByLocation`
2. Mirror this in both compressed and uncompressed validation prompts.

Expected result:
- Model can emit resolution markers without validator drift.

### Phase 2 - Resolved-Hostile-Aware DM Note

1. In `utils/multi_pc_dm_note.py` and `main.py`, when building location context:
   - Read `currentLocationId` and `worldConditions.resolvedHostilesByLocation`.
   - If current location is resolved, suppress unconditional active-threat sentence.
   - Replace with resolved-safe guidance:
     - "Resolved Hostile State: This hostile guardian has been appeased. Do not re-initiate unless provoked."
2. Keep default active-threat sentence for unresolved locations.

Expected result:
- Narrator no longer receives contradictory instruction to re-hostilize resolved guardian scenes.

### Phase 3 - Validation Guardrail for Loop Prevention

Add compact validation rule to block passive re-loop responses:

- If player expresses travel intent from current location and response re-blocks with `actions: []` despite resolved marker and no provocation, mark invalid and require action/state sync.

Expected result:
- Prevents repeated "same blocker, no action" narrative loops.

### Phase 4 - Regression Coverage

Add tests for:

1. Prompt contract includes `resolvedHostilesByLocation` in updatePartyTracker params.
2. DM-note output for resolved location omits active-threat line and includes resolved-safe line.
3. DM-note output for unresolved location keeps active-threat line.
4. Existing Prompt 1-5 tests remain green.

## Acceptance Criteria

1. Successful parlay + marker persistence allows travel out of V04 without repeated Bloodshadow blocker narration.
2. No regression to unresolved-hostile behavior at other locations.
3. Validation accepts correct marker payloads and rejects passive blocker loops.
4. All relevant tests pass.

## Risks and Mitigations

- Risk: Over-suppressing valid hostile behavior globally.
  - Mitigation: Gate suppression strictly by `resolvedHostilesByLocation[currentLocationId] == true`.

- Risk: Prompt/validator mismatch.
  - Mitigation: Update both compressed and uncompressed validation prompt contracts together.

- Risk: Legacy saves missing marker map.
  - Mitigation: Fail-open to existing unresolved behavior when key absent.

## Initial Builder Prompt (Phase 1)

Implement Prompt 1 of this plan.

Goal:
- Align model/validator action contracts for resolved hostile marker persistence.

Files in scope:
1. `prompts/system_prompt_compressed.txt`
2. `prompts/validation/validation_prompt_compressed.txt`
3. `prompts/validation/validation_prompt.txt`

Requirements:
1. Extend `@ACTION_PARAMS.updatePartyTracker` docs to include optional:
   - `resolvedHostilesByLocation`: dict (top-level)
   - `worldConditions`: dict (nested update path; may contain `resolvedHostilesByLocation`)
2. Keep all existing keys and semantics unchanged.
3. Add one concise validation note that these forms are valid for peaceful guardian resolution state sync.
4. Additive edits only, ASCII only.

Validation:
- Confirm all three prompt files contain the new parameter guidance.
- Run prompt contract tests if available.

Return:
- Exact snippets changed
- File/line references
- Any impacted tests and results
