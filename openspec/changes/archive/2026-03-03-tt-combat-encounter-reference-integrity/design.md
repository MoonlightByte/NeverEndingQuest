## Context

Current runtime behavior is intentionally fail-closed in tabletop mode: missing monster stat files abort encounter generation. This protects against hallucinated monster creation, but validation does not currently catch authored reference gaps before runtime.

The ingest pipeline already has strict quarantine semantics through `ModuleValidator`, so adding a new validator rule is the lowest-risk, highest-leverage integration point.

## Goals

1. Catch unresolved area monster references before gameplay.
2. Enforce the same integrity rule for ingest and module activation/copy paths.
3. Surface clear, actionable failure context in chat when runtime still encounters missing monster files.
4. Eliminate false combat narration impression on failed `createEncounter`.

## Non-Goals

1. Do not re-enable auto-creation of missing monsters in tabletop mode.
2. Do not change combat mechanics, initiative flow, or enemy batch semantics.
3. Do not redesign all validation reporting categories beyond this targeted rule.

## Decisions

### 1) Add dedicated validator category for cross-reference integrity

- MUST add `reference_integrity` result category in `ModuleValidator`.
- MUST scan area/location monster references and verify corresponding monster file existence.
- SHOULD normalize names using the same slug logic used by combat loader (`lower`, trim, spaces->underscore, apostrophe removal).

Rationale: keeps checks deterministic and aligned with runtime lookup behavior.

### 2) Reuse strict ingest quarantine path

- MUST rely on existing importer strict behavior: validation fail => quarantined.
- MUST ensure new `reference_integrity` errors are included in returned validation errors.

Rationale: avoids duplicate ingest policy logic and keeps one source of truth.

### 3) Add activation/copy preflight gate

- MUST run module validation preflight at module activation/copy entry points.
- MUST block activation when unresolved references are found.
- SHOULD emit concise `[SYSTEM]` summary and detailed logs/sidecar errors.

Rationale: some modules may be manually copied and bypass ingest; activation gate closes that gap.

### 4) Improve runtime failure surfacing

- MUST return actionable missing-file context in `createEncounter` error message when available.
- MUST append `[SYSTEM]` message to conversation history on failure (existing path retained, message quality improved).

Rationale: gameplay operator should get direct fix instructions without reading subprocess logs.

### 5) Gate narration for combat-start action failure

- MUST prevent combat-flavored narration from being emitted when response includes `createEncounter` and action fails.
- SHOULD keep existing behavior unchanged for non-combat actions.

Rationale: prevents perceived hallucinated combat while preserving current narration pipeline for other actions.

## Risks and Trade-offs

1. **False positives from normalization drift**
   - Mitigation: implement single shared helper used by validator and error formatter.

2. **Activation gate may block legacy modules**
   - Mitigation: explicit error list with expected file paths; fail fast is intentional for data integrity.

3. **Narration gating could alter user-facing pacing**
   - Mitigation: limit to createEncounter-failure path only; add regression coverage.

## Migration Plan

1. Implement validator rule and reporting.
2. Wire into ingest and activation/copy validation gates.
3. Improve runtime error_message extraction from builder failure output.
4. Add narration gating for failed createEncounter.
5. Add tests and verification commands.

## Rollback Plan

1. Remove `reference_integrity` check from `run_all_validations()`.
2. Revert activation preflight gate hook.
3. Revert createEncounter error-message enrichment and narration gate.

Rollback preserves current fail-closed runtime behavior in `combat_builder.py`.
