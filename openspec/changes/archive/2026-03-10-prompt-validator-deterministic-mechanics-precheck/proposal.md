## Why

Prompt/validator contract alignment reduced action-shape drift, but the validation pipeline still relies primarily on the LLM validator for mechanical sanity checks in `updateCharacterInfo` payloads. This allows avoidable failure modes such as explicit HP totals above max HP, explicit spell-slot ratios with impossible values, or explicit item removals that exceed known quantities to slip into retries and occasionally pass in ambiguous contexts.

This change adds a deterministic precheck layer for explicit mechanics contradictions before LLM validation. It is a bounded, fail-closed pass for parseable contradictions and fail-open for unparseable freeform text.

## What Changes

- Add deterministic mechanics precheck utility for `updateCharacterInfo` actions.
- Enforce explicit contradiction guards for:
  - HP target values outside `[0, maxHitPoints]` when explicit totals are present.
  - Spell-slot ratio values where explicit `current/max` has `current > max` or negative values.
  - Explicit item-removal quantities that exceed known tracked quantities (equipment/ammunition) when parseable.
- Integrate precheck into `validate_ai_response()` before LLM validator calls.
- Add focused regression tests for helper behavior and validation-pipeline integration.

## Covered Scope

This change only covers deterministic prechecks for explicit, parseable mechanics contradictions in `updateCharacterInfo` changes.

Out of scope:
- broad natural-language semantics parsing
- combat architecture changes
- changes to save/module contracts (already handled separately)
- replacing LLM validator with deterministic validator

## Capabilities

### New Capabilities
- `tt-deterministic-mechanics-precheck`: explicit mechanics contradictions in narrator-authored `updateCharacterInfo` deltas MUST be blocked deterministically before LLM validation.

### Modified Capabilities
- None in this phase.

## Impact

- Affected runtime:
  - `main.py`
  - new utility under `utils/`
- Affected tests:
  - new deterministic precheck regression tests under `scripts/`
- Risk profile:
  - low-to-medium, mitigated by fail-open parsing behavior and explicit-only checks

## Acceptance Criteria

- Deterministic precheck runs before LLM validation in `validate_ai_response()`.
- Explicit contradictory HP/slot/item-removal deltas are rejected with deterministic reason text.
- Non-parseable or ambiguous change text remains fail-open (does not block solely due parsing uncertainty).
- Targeted tests cover pass/fail behavior for the three covered contradiction classes.
