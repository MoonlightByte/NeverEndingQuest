## 1. Contract and Data Model

- [x] 1.1 Extend `schemas/loca_schema.json` so location `npcs[]` MAY include additive `sceneEntity` metadata.
- [x] 1.2 Add a shared runtime helper (new `utils/scene_entity_contract.py`) that reads current-location scene-entity metadata and exposes combat-validity, manifestation, violence-policy, and combat-proxy decisions.
- [x] 1.3 Keep the new metadata optional so unannotated modules preserve current behavior.

## 2. Combat Guard and Error Surfacing

- [x] 2.1 Add a pre-builder createEncounter guard that detects when a requested monster label is actually a current-scene authored entity with `sceneEntity` metadata.
- [x] 2.2 Surface a dedicated non-combat-valid scene-entity error instead of a generic unauthorized-monster failure when that guard triggers.
- [x] 2.3 Preserve existing monster authorization and hydration behavior for true monsters.
- [x] 2.4 Fix any misleading success logging in the createEncounter path so failed encounter builds do not emit premature success messages.

## 3. Violence Resolution Runtime

- [x] 3.1 Add bounded runtime handling for `incorporeal_no_effect` scene entities so physical attacks can narrate no-effect resolution without starting combat.
- [x] 3.2 Add bounded runtime handling for `helpless_kill_else_escalate` scene entities, reusing deterministic scene-state mutation paths for helpless/nonresisting harm.
- [x] 3.3 Require explicit `combatProxy` data for escalated combat against scene entities and fail closed when escalation is needed but proxy data is missing.

## 4. Prompt and Validation Parity

- [x] 4.1 Update narrator contract wording so visible scene entities are not automatically treated as combat-valid monsters.
- [x] 4.2 Update validation guidance so no-effect attacks on incorporeal scene entities can remain narration-only without false createEncounter pressure.
- [x] 4.3 Keep combat prompt changes narrow and avoid broad encounter-generation rewrites.

## 5. Module Annotation and Regression Coverage

- [x] 5.1 Annotate `Red (The Crimson Binder)` in `Night_of_the_Restless_Dead` as the proving-case incorporeal scene-only entity.
- [x] 5.2 Add targeted regressions for Red-style no-effect attack resolution and scene-entity createEncounter rejection.
- [x] 5.3 Add targeted regressions for corporeal helpless-kill-else-escalate behavior.
- [x] 5.4 Keep existing combat and scene-presence regressions green.

## 6. Verification

- [x] 6.1 Run targeted regression tests for scene-entity combat validity and violence resolution.
- [x] 6.2 Run `python3 -m py_compile` on all touched Python files.
- [x] 6.3 Run relevant schema validation for touched module data and `schemas/loca_schema.json` consumers.
- [x] 6.4 Run `openspec validate scene-entity-combat-validity-contract`.
