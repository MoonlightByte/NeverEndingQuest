## Why

This change is the Phase 1B follow-up to `prompt-validator-contract-alignment`. After `rest` parity, the highest-value remaining prompt/runtime drift is in save-management actions and `createNewModule`.

Today the compressed validator still documents stale save contracts like `saveName`, while runtime executes `saveGame` with `description` and `saveMode`, and executes `restoreGame` and `deleteSave` with `saveFolder`. `createNewModule` has a different kind of drift: prompts describe a narrative-driven action, but the compressed validator still expects a rigid `moduleName` and `startingLocation` shape that does not match runtime.

These mismatches create false validation failures, make the narrator harder to steer, and obscure the real runtime contract.

## What Changes

- Align save-management action contracts across compressed/uncompressed prompts, validator text, and runtime expectations.
- Align `createNewModule` contract across prompts and validator to the current narrative-driven runtime behavior.
- Add parity regression coverage for save-management actions and `createNewModule` across both compressed and uncompressed prompt variants.
- Keep runtime as the operational baseline for this slice unless an obvious bug is discovered.
- Preserve merge safety and backward compatibility; add compatibility shims only if needed to keep existing side paths stable while prompts are corrected.
- Defer deterministic HP/slot/inventory prechecks and any structured-ops redesign to later phases.

## Covered Action Set

This change explicitly covers only:
- `saveGame`
- `restoreGame`
- `listSaves`
- `deleteSave`
- `createNewModule`

All other prompt/validator drift is out of scope for this change.

## Capabilities

### New Capabilities
- `tt-save-actions-contract`: save-management actions MUST use one consistent narrator/validator/runtime contract.
- `tt-create-module-action-contract`: `createNewModule` MUST use a validator contract that matches the narrative-driven runtime handoff.

### Modified Capabilities
- None in this phase.

## Impact

- Affected prompts:
  - `prompts/system_prompt_compressed.txt`
  - `prompts/system_prompt.txt`
  - `prompts/validation/validation_prompt_compressed.txt`
  - `prompts/validation/validation_prompt.txt`
- Affected runtime:
  - `core/ai/action_handler.py`
  - `core/generators/module_builder.py` (reference-only audit unless shim needed)
- Affected tests:
  - new parity regression coverage for save-management actions and `createNewModule`
  - parity assertions for both prompt variants and both validator variants
- Merge safety:
  - MUST prefer small prompt edits and additive tests
  - MUST avoid unrelated module-builder rewrites or save-system behavior changes in this phase
- Rollout risk:
  - low-to-medium for prompt/validator edits
  - medium if stale tests or side paths still assume `saveName` or rigid `createNewModule` params
- Fallback strategy:
  - if prompt correction exposes a legacy side path, add the smallest runtime compatibility shim that preserves current behavior
  - if broader prompt/validator drift is discovered outside the covered actions, record it for a later slice rather than widening this change

## Acceptance Criteria

- Save-management action contracts are aligned across system prompt, validation prompt, and runtime behavior for both compressed and uncompressed prompt variants.
- Validator guidance no longer requires `saveName` for `restoreGame` or `deleteSave` when runtime uses `saveFolder`.
- `createNewModule` validator guidance accepts the narrative-driven runtime contract and does not require rigid `moduleName` and `startingLocation` fields as the only valid shape.
- Regression coverage fails if any prompt variant drifts from the covered runtime contracts.
- This change remains scoped to the covered action set only.
