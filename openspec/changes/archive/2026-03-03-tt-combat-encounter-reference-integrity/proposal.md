## Why

Tabletop combat currently fail-closes when encounter content references a monster that has no module stat file. This is correct for safety, but two gaps remain:

1. Missing monster references are discovered at runtime instead of at module validation/ingest time.
2. Users can see combat-flavored narration before the failed `createEncounter` action returns, which feels like LLM hallucinated combat.

Recent failure: `Cornfield Shadow` is referenced in area content for `The_Pumpkin_Kings_Curse` but `modules/The_Pumpkin_Kings_Curse/monsters/cornfield_shadow.json` is missing. Encounter build aborts and combat never starts.

## What Changes

1. Add monster-reference integrity validation to `ModuleValidator`.
2. Enforce this validation in ingest and module activation/copy flows.
3. Improve runtime failure surfacing with explicit `[SYSTEM]` error context for missing monster files.
4. Prevent pre-action combat narration leak on failed `createEncounter`.

## Capabilities

### New capability: `tt-monster-reference-integrity-validation`

- Add deterministic cross-reference check: every `areas/*.json` monster reference resolves to `monsters/<normalized>.json`.
- Validation failures include area/location context and expected file path.
- Validation report includes a dedicated `reference_integrity` section.

### New capability: `tt-ingest-activation-validation-gate`

- Strict ingest quarantines modules with unresolved monster references.
- Module activation/copy-to-campaign path runs validator preflight and blocks activation on unresolved references.

### Modified capability: `tt-createencounter-failure-surfacing`

- `createEncounter` failure returns actionable `error_message` with missing monster/stat-file detail.
- Chat gets explicit `[SYSTEM]` failure message.
- Combat narration does not print when `createEncounter` fails.

## Impact

- Prevents runtime combat-start surprises caused by authoring reference gaps.
- Preserves existing fail-closed tabletop safety against hallucinated monsters.
- Improves operator UX during gameplay tests and ingest workflows.
- Keeps single-player and unrelated action flows unchanged.
