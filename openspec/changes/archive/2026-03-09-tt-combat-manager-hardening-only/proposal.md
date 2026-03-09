## Why

The current test build needs safer iteration on TABLETOP MODE combat behavior without taking on a full upstream-wide combat manager rewrite. Recent fixes are correct, but editing `core/managers/combat_manager.py` remains fragile for builder agents due to deeply nested control flow and indentation-sensitive blocks.

## What Changes

- Isolate TABLETOP MODE `/init` two-group initiative gate into a focused helper boundary while preserving existing behavior.
- Isolate `/init` two-group initiative gate handling into a dedicated helper path with stable inputs/outputs.
- Preserve current TT ownership split for state sync: `normalize_phase1_initiative(...)` stays in `combat_manager.py`, while marker/roster helpers stay in `combat_state_sync.py`.
- Keep host-file edits minimal and additive, with `# TABLETOP MODE:` markers for merge clarity.
- Add a builder regression syntax guard script that compiles touched Python files after each patch step.
- Execute compile-guard setup first in implementation order to reduce indentation-regression risk before combat-manager edits.
- Preserve single-player compatibility and fail-open behavior for missing/legacy fields.

## Capabilities

### New Capabilities
- `tt-combat-manager-gate-isolation`: `/init` two-group initiative gate and TT phase-marker handling are isolated behind a helper boundary without behavior drift.
- `tt-builder-patch-compile-guard`: deterministic compile-check utility for builder workflows validates touched Python files and fails fast on syntax errors.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `core/managers/combat_manager.py`
  - `core/managers/combat_state_sync.py`
  - `scripts/check_builder_patch_syntax.py` (new)
- Runtime impact: none intended; behavior-preserving extraction only.
- Risk: moderate refactor risk in combat loop routing.
  - Fallback strategy (MUST): phase-scoped rollback and fail-open retention.
- Merge safety:
  - MUST preserve upstream flow where possible.
  - MUST confine refactor to TT-owned branches in current test build.
- SP/MP compatibility:
  - MUST keep single-player behavior unchanged.
  - SHOULD improve multi-PC reliability by reducing fragile inline logic.
