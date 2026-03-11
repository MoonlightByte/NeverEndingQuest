## Why

`combat-runtime-authority-and-efficiency`, `combat-structured-pc-allied-ops-pilot`, and `combat-save-concentration-contract` completed the first safe combat hardening wave: canonical combat authority, slimmer validation packets, structured PC/allied mechanics, and explicit save/check pause contracts. The remaining planned follow-on in Workstream H is the expanded deterministic guard set.

Combat still relies on probabilistic validation for several explicit contradiction classes that should be rejected deterministically before they become retries or runtime drift. The highest-value remaining domains are explicit HP/state contradictions, explicit ammo and spell-slot underflow, and explicit phase-integrity violations.

## What Changes

- Add combat-specific deterministic guard contracts for explicit mechanical contradiction classes.
- Add combat-specific deterministic guard contracts for explicit phase-integrity contradictions.
- Preserve fail-open behavior for ambiguous or unparseable combat text.
- Add focused combat contract tests before any helper/runtime tightening.
- Keep prompt/validator wording changes optional and narrow, only if implementation reveals contract drift.

## Covered Scope

This change explicitly covers:
- deterministic combat guards for explicit contradictions only
- additive helper/runtime tightening in current combat validation paths
- focused tests for mechanical contradiction and phase-integrity guard domains
- fail-open protection for ambiguous combat narration

Out of scope:
- `updateEncounter.ops`
- roll resolution or dice-engine behavior
- broad combat prompt rewrites
- style/tactics validation
- non-combat narrator guard expansion

## Capabilities

### New Capabilities
- `tt-combat-mechanics-contradiction-guards`: combat deterministic guards SHALL reject explicit HP/state, ammo, and spell-slot contradictions when canonical state makes the contradiction unambiguous.
- `tt-combat-phase-integrity-guards`: combat deterministic guards SHALL reject explicit forbidden-phase actor, premature stop, illegal exit, and illegal round-increment contradictions when phase state is authoritative.

### Modified Capabilities
- `tt-combat-validator-mechanical-truth-pack`
- `tt-combat-validation-efficiency-routing`

## Risks and Fallback

- MUST preserve fail-open behavior when combat text is ambiguous, incomplete, or not confidently parseable.
- MUST keep checks bounded to explicit contradictions backed by authoritative combat/runtime state.
- MUST avoid broad natural-language interpretation or tactical-style policing.
- SHOULD prefer deterministic negative tests before prompt wording changes.
- SHOULD treat prompt/validator edits as parity work only if implementation reveals drift.

Fallback strategy:
- If a guard produces false positives in testing, narrow the deterministic matcher before broadening prompt language.
- If a contradiction class cannot be enforced without ambiguity, defer it instead of forcing a brittle guard.

## Impact

- Expected runtime touchpoints:
  - `core/managers/combat_manager.py`
  - `core/ai/action_handler.py`
  - existing combat deterministic helper paths or a narrow combat-specific helper
- Expected tests:
  - new `scripts/test_combat_expanded_deterministic_guards_contract.py`
  - existing `scripts/test_multi_pc_combat.py`
  - existing `scripts/c5_regression_combat.py`
- Possible narrow prompt parity touchpoints if needed:
  - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
  - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`

## Acceptance Criteria

- OpenSpec artifacts lock the explicit combat contradiction domains and fail-open boundaries.
- Contract tests exist before helper/runtime implementation.
- Runtime implementation remains bounded to explicit contradiction classes only.
- Existing combat regressions remain green.
- The change validates cleanly and is ready for stepwise builder execution.
