## Why

The Narrator DM stack currently has contract drift between the system prompt, validation prompt, and runtime action handler. The most visible example is rest handling: the narrator prompt and Python runtime use a `rest` action, while the compressed validator still expects direct `updateCharacterInfo` recovery behavior. This mismatch increases retries, slows turns, and creates avoidable 5e noncompliance.

This change is needed now because the prompt/validator stack is becoming harder to reason about as more deterministic guards and tabletop-specific rules are added. Before larger mechanics refactors, the action contract must be made explicit and internally consistent.

This OpenSpec change is intentionally a narrow Phase 1A slice. It focuses on `rest` contract parity and the regression harness needed to keep future prompt edits aligned with runtime behavior.

## What Changes

- Align supported narrator action contracts across compressed/uncompressed prompts and runtime handling.
- Make `rest` a first-class validated action across prompt, validator, and runtime behavior.
- Add prompt/runtime parity regression coverage so action-name and parameter-shape drift is caught automatically.
- Clarify the first implementation slice for the larger prompt/validator hardening program without changing the broader narrative architecture yet.
- Define the covered action set for this change explicitly as `rest` only; save/restore/list/delete-save and `createNewModule` contract cleanup are deferred to the next contract-alignment slice.
- Require parity checks to cover both compressed and uncompressed prompt copies because runtime and validation may load different prompt variants.
- SHOULD preserve current retry hygiene and fail-closed deterministic guard behavior while reducing false validation failures.
- MUST remain merge-safe and backward compatible with single-player and tabletop mode.

## Capabilities

### New Capabilities
- `tt-action-contract-parity`: supported narrator actions MUST use one consistent contract across prompts, validator, and runtime.
- `tt-rest-action-contract`: rest behavior MUST be expressed and validated as the dedicated `rest` action with matching runtime semantics.

### Modified Capabilities
- None in this phase.

## Impact

- Affected prompts:
  - `prompts/system_prompt_compressed.txt`
  - `prompts/system_prompt.txt`
  - `prompts/validation/validation_prompt_compressed.txt`
  - `prompts/validation/validation_prompt.txt`
- Affected runtime:
  - `main.py`
  - `core/ai/action_handler.py`
- Affected tests:
  - new regression coverage for prompt/runtime parity and rest contract alignment
  - parity assertions for both `prompts/system_prompt_compressed.txt` and `prompts/system_prompt.txt`
  - parity assertions for both validation prompt variants
- Merge safety:
  - MUST prefer small prompt edits and additive tests
  - MUST avoid unrelated changes to combat flow or large mechanics rewrites in this phase
- Rollout risk:
  - low-to-medium for prompt edits
  - medium for validator/runtime parity because stale assumptions may exist in tests or legacy paths
- Fallback strategy:
  - if parity changes expose legacy dependencies, keep compatibility shims in runtime while prompts and tests are brought into alignment
  - if broader action drift is discovered outside `rest`, record it for the next parity slice rather than widening this change mid-build
- SP/MP compatibility:
  - MUST preserve both single-player and tabletop mode behavior
  - SHOULD avoid introducing mode-specific action contracts for this phase

## Acceptance Criteria

- `rest` contract text is aligned across system prompt, validation prompt, and runtime behavior for both compressed and uncompressed prompt variants.
- Regression coverage fails if any covered prompt variant reintroduces narrator-authored `updateCharacterInfo` as the primary `rest` contract.
- This change remains scoped to `rest` parity plus parity-test scaffolding; save/restore/list/delete-save and `createNewModule` drift are explicitly deferred.
