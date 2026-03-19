## Why

Combat creation currently fail-closes whenever a module-authored creature is missing a local monster JSON file, even if the authored module content clearly establishes that creature as canon for the scene. This blocks live play on valid authored threats like `Cultist` in `Night_of_the_Restless_Dead`, while the current runtime cannot distinguish "authorized but missing stat file" from a true narration-only hallucination.

## What Changes

- Add a runtime authorization layer that derives a module-authoritative monster roster from authored module content before encounter creation.
- Allow encounter generation to hydrate missing monster stat files only when the monster is authorized by authored module content.
- Preserve fail-closed rejection for monsters that appear only in runtime narration and cannot be validated against module-authored content.
- Distinguish encounter failure classes so operators can tell the difference between:
  - authorized monster missing a stat file but hydration failed, and
  - unauthorized monster rejected as hallucinated encounter content.
- Keep single-player and multi-player combat startup behavior backward compatible once a monster is already resolved.
- Non-goal: this change does NOT widen encounter authority to arbitrary LLM narration, and it does NOT remove existing monster hallucination protections.

## Capabilities

### New Capabilities
- `tt-module-authorized-monster-hydration`: Runtime encounter creation SHALL auto-hydrate missing monster files only for creatures validated against authored module content.

### Modified Capabilities
- `tt-createencounter-failure-surfacing`: Encounter failure reporting SHALL distinguish authorized-hydration failure from unauthorized monster rejection.

## Impact

- Affected code:
  - `core/generators/combat_builder.py`
  - `core/ai/action_handler.py`
  - supporting monster-authorization helpers under `utils/` or `core/validation/`
  - targeted regression coverage under `scripts/`
- Systems affected:
  - tabletop combat startup
  - monster resolution/lookup
  - authored content validation boundary between Python truth and runtime narration
- Merge safety:
  - MUST prefer isolated helper/module additions and minimal `# TABLETOP MODE:` hooks in host files.
- SP/MP compatibility:
  - MUST preserve existing success behavior for encounters whose monster files already exist.
  - SHOULD keep single-player fallback behavior intact except where a true unauthorized monster must still fail closed.
- Rollout risk:
  - Incorrect authorization heuristics could widen the hallucination surface.
  - Fallback strategy MUST remain fail-closed when authorization is ambiguous or hydration fails.
