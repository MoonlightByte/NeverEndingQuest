## Context

`Night_of_the_Restless_Dead` was ingested as a playable baseline but remains narratively thin and mostly linear. Current verification status for expansion planning:

- Ingest sidecar audit gate currently fails because no sidecar artifact is present for slug `Night_of_the_Restless_Dead`.
- Strict module schema validation is blocked in this environment because `jsonschema` is unavailable.

This design adds narrative depth while preserving ingest and validation compatibility contracts.

## Goals

- Add meaningful branching narrative possibilities without breaking existing module progression.
- Keep the horror tone morally gray (not purely heroic, not purely villainous).
- Keep module standalone with optional minor worldline references.
- Keep content edits additive and validator-safe.

## Non-Goals

- Re-running or redesigning the ingest pipeline itself.
- Introducing hard dependency on Pumpkin King or Thornwood completion.
- Replacing current undead creature classes with a new roster.
- Introducing core engine or web-interface changes.

## Decisions

### D1 - Additive Narrative Expansion on Existing Backbone

- MUST preserve canonical PP001->PP007 sequence so baseline traversal still works.
- MUST add branch metadata as additive fields (no required key removal/rename).
- SHOULD express branches through explicit player choices and discoverable clues.

### D2 - Morally Gray Climax Contract

- MUST support at least three valid climax outcomes: aid cult, oppose cult, negotiated third path.
- MUST ensure each outcome has an explicit consequence payload in module plot/context.
- SHOULD keep cult portrayal morally mixed (desperate victims + harmful actors).

### D3 - Standalone First, Cross-Reference Second

- MUST keep all cross-module references optional and non-blocking.
- MUST keep this module completable without loading Pumpkin King or Thornwood modules.
- SHOULD include minor rumor/lore hooks that can be acknowledged by those modules later.

### D4 - Contained Ring Thread

- MUST keep ring arc scope bounded to this module plus one future module (TBC).
- MUST avoid introducing a world-scale mandatory ring quest in this change.
- SHOULD record ring state in additive context fields for future continuity.

### D5 - Creature Roster Stability

- MUST keep current undead baseline (zombies, skeletons, giant spider).
- MUST avoid adding new creature classes unless explicitly requested in a later change.
- SHOULD increase horror depth via motive, environment, and consequence, not roster churn.

### D6 - Ingest and Validation Gates

- MUST run `homebrew_sidecar_audit` gate and report explicit degraded state if sidecar is missing.
- MUST run module validation gate; if `jsonschema` missing, run documented degraded fallback checks and report gap.
- SHOULD keep verification output deterministic and attached to change notes.

## Risk and Mitigation

- Risk: Additive branch fields drift from module conventions.
  - Mitigation: confine new keys to narrative metadata blocks; preserve existing required keys.
- Risk: Cross-module hooks become hidden dependencies.
  - Mitigation: every hook phrased as optional rumor/context, never required objective.
- Risk: Environment blocks strict validation.
  - Mitigation: explicitly record degraded status and re-run strict checks when `jsonschema` is available.

## Verification Strategy

- Run ingest audit: `python3 scripts/homebrew_sidecar_audit.py --slug Night_of_the_Restless_Dead --require-success --json`.
- Run strict validator when available: `python3 core/validation/validate_module_files.py --module Night_of_the_Restless_Dead --json`.
- Degraded fallback when strict validator is unavailable:
  - JSON parse check for modified files.
  - Optional gameplay audit check if monster references are changed.
- Final OpenSpec gate: `openspec validate night-restless-dead-branching-horror-expansion`.
