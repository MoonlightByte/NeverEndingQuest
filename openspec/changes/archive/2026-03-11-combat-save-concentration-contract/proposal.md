## Why

`combat-structured-pc-allied-ops-pilot` completed the combat-side mechanics-routing follow-on after `combat-runtime-authority-and-efficiency`. Combat prompts now prefer structured `updateCharacterInfo` payloads for PC/allied state updates, but combat save/check pauses still rely heavily on prose-era narration and ad hoc concentration wording.

The next narrow slice is to align multi-PC combat with the already-established `requestRoll` and concentration DC contracts. Combat should prefer explicit `requestRoll` actions for saving throws, ability checks, skill checks, and concentration saves, while preserving current pause semantics and prose compatibility during migration.

## What Changes

- Add combat-specific prompt and validator contract guidance that prefers `requestRoll` for saves/checks/concentration pauses.
- Lock combat stop-after-request semantics so the same response does not narrate contingent player-roll success or failure.
- Lock combat concentration request wording to the deterministic 5e DC formula `max(10, floor(damage / 2))`.
- Preserve prose-only compatibility during migration so existing combat turns remain valid while the structured contract rolls out.
- Add focused combat contract tests plus targeted regression verification.

## Covered Scope

This change explicitly covers:
- multi-PC combat prompt and validator alignment for `requestRoll`
- combat-specific concentration request contract wording
- focused combat contract tests for pause semantics and deterministic concentration DC expectations
- narrow runtime inspection and only minimal runtime alignment if current scaffolding proves insufficient

Out of scope:
- full roll-result ingestion or automatic resolution
- enemy-side `updateEncounter.ops`
- combat initiative redesign
- broad combat runtime rewrites
- deprecating prose-only save/check narration in this phase

## Capabilities

### New Capabilities
- `tt-combat-request-roll-routing`: multi-PC combat prompt and validator contracts SHALL prefer `requestRoll` for saving throws, ability checks, skill checks, and concentration pauses while preserving prose compatibility during migration.
- `tt-combat-concentration-request-dc`: multi-PC combat concentration requests SHALL use the deterministic DC formula `max(10, floor(damage / 2))` and SHALL stop after issuing the request.

### Modified Capabilities
- `tt-request-roll-contract`
- `tt-concentration-dc-contract`

## Risks and Fallback

- MUST preserve current combat pause semantics and never narrate contingent player-roll outcomes in the same response as `requestRoll`.
- MUST preserve prose-only compatibility during migration.
- MUST keep scope narrow: no full dice engine, no roll resolution rewrite, no enemy contract widening.
- SHOULD prefer combat prompt/validator parity and tests before any runtime edits.
- SHOULD treat runtime work as optional if current scaffolding already satisfies combat needs.

Fallback strategy:
- If combat regressions appear, revert combat prompt/validator `requestRoll` preference edits before touching runtime behavior.
- If runtime inspection finds no combat-specific gap, close the runtime step as a no-op rather than widening scope.

## Impact

- Affected prompts:
  - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
  - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
  - mirror combat prompt files only as needed for parity/docs
- Expected runtime touchpoints:
  - `core/managers/combat_manager.py`
  - `core/ai/action_handler.py`
- Expected tests:
  - new `scripts/test_combat_save_concentration_contract.py`
  - existing `scripts/test_save_concentration_contract.py`
  - existing combat regressions (`scripts/test_multi_pc_combat.py`, `scripts/c5_regression_combat.py`)

## Acceptance Criteria

- Combat prompt and validator explicitly prefer `requestRoll` for saves/checks/concentration pauses.
- Combat contract enforces stop-after-request and no same-response contingent outcome narration.
- Combat concentration requests lock the deterministic DC formula `max(10, floor(damage / 2))`.
- Prose-only compatibility remains documented during migration.
- The new change validates cleanly and targeted regressions remain green.
