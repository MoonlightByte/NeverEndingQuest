## Why

The prompt-validator hardening work now has aligned action contracts, compressed prompt authority, validation routing, truth packs, and structured character ops. The next gap in `plans/prompt-validator-fix.md` is that player-facing saves/checks still depend on prose-only narration, while concentration DC logic remains documented in text rather than locked as a deterministic contract.

This change introduces a lightweight first-class roll-request contract and a deterministic concentration DC contract so later runtime work can reduce ambiguity without turning the game into a full dice-engine rewrite.

## What Changes

- Add a lightweight `requestRoll` action contract for player-facing saving throws and checks.
- Lock a minimal payload shape for `requestRoll` that is explicit enough for validation and future runtime helpers.
- Define a deterministic concentration DC contract using the 5e rule `max(10, floor(damage / 2))`.
- Update prompt and validator contract text to recognize the new roll-request contract while preserving current prose compatibility during migration.
- Add focused tests that lock the contract, compatibility expectations, and concentration DC rule before broader runtime changes.

## Covered Scope

This change explicitly covers:
- prompt/validator/runtime contract scaffolding for `requestRoll`
- deterministic concentration DC contract and helper expectations
- backward-compatible migration from prose-only save/check requests
- builder-ready phased execution prompts for a narrow implementation sequence

Out of scope:
- a full dice engine
- automatic roll result resolution
- combat initiative redesign
- broad combat prompt rewrites outside the narrow save/check contract touchpoints
- deprecating prose-only save/check narration in this phase

## Capabilities

### New Capabilities
- `tt-request-roll-contract`: player-facing saves and checks MUST support a lightweight first-class `requestRoll` action contract without breaking prose-only compatibility during migration.
- `tt-concentration-dc-contract`: concentration save DC calculations MUST follow a deterministic 5e contract that later runtime helpers can share.

### Modified Capabilities
- None.

## Risks and Fallback

- MUST preserve current prose-only save/check narration as a compatibility path until targeted runtime and prompt tests are passing.
- MUST keep concentration DC logic deterministic and testable, not implied by freeform prompt wording alone.
- SHOULD prefer `requestRoll` as the new action name unless repo inspection during implementation reveals an already-established canonical name that can satisfy the same contract without widening scope.
- SHOULD keep the payload minimal so builders do not accidentally create a full roll-resolution system.

## Merge-Safety and SP/MP Compatibility

- MUST preserve single-player behavior and existing tabletop combat pause semantics.
- MUST use minimal host-file hooks and mark any required host edits with `# TABLETOP MODE:` comments.
- SHOULD keep combat-specific changes additive so upstream merge friction stays low.

## Impact

- Affected prompts:
  - `prompts/system_prompt_compressed.txt`
  - `prompts/validation/validation_prompt_compressed.txt`
- Expected runtime touchpoints:
  - `main.py`
  - `core/managers/combat_manager.py`
  - `core/ai/action_handler.py`
  - possible new helper under `utils/` or `core/validation/`
- Expected tests:
  - `scripts/test_save_concentration_contract.py`

## Acceptance Criteria

- A first-class roll-request contract is defined in OpenSpec and builder prompts.
- The contract locks a minimal payload shape for player-facing saves/checks.
- The concentration DC rule is specified as `max(10, floor(damage / 2))`.
- The implementation plan preserves prose-only compatibility while the structured path is introduced.
- The change artifacts are ready for phased builder execution.
