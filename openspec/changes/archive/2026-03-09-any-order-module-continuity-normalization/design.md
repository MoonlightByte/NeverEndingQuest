## Context

The project needs two compatible play styles at once:
- standalone modules (drop-in, no external dependencies), and
- campaign trajectories where earlier outcomes influence later modules.

Current module contracts encode this unevenly. To scale future homebrew ingest, continuity must be normalized into deterministic keys that can be linted and audited.

## Goals

1. Define an additive continuity schema usable by all modules.
2. Normalize homebrew ingest outputs into that schema.
3. Validate continuity in readiness workflows and bulk module gates.
4. Keep fallback-safe behavior so modules remain playable in isolation.

## Contract: Continuity v1

Continuity v1 is additive and uses normalized keys that do not replace prose.

### Module Context Keys

- `continuity_version`: string, expected `"v1"`
- `entry_state_variants`: object with `cold_start`, `partial_context`, `late_arc`
- `cross_module_refs`: array of normalized references
- `prereq_paths`: object with `any_of` alternatives for major unlocks
- `standalone_fallback`: object listing in-module fallback clue sources

### Module Plot Keys

- `branch_metadata.outcomes[*].cross_module_impact`: typed impact object
- Optional outcome-level flags:
  - `faction_stance`
  - `artifact_state`
  - `survivor_state`
  - `future_hook`

### Normalized Reference Shape

Each `cross_module_ref` item should support:
- `target_module`
- `entity_id`
- `relation`
- `confidence` (`high|medium|low`)
- `notes` (optional)

## Ingest Integration

`scripts/homebrew_ingest_dev.py` gains a continuity normalization stage:

1. Build continuity draft from source/module context.
2. Canonicalize entity/module identifiers.
3. Fill missing fallback-safe keys.
4. Emit `continuity_contract` section in sidecar payload.

Policy:
- Start in warn-first mode for unresolved aliases.
- Hard-fail when required continuity fields are absent in strict mode.

## Validation Integration

Readiness validation gains continuity gate:

- New audit entrypoint: `scripts/module_continuity_audit.py`.
- `scripts/audit_module_readiness.py` invokes continuity gate in strict contract.
- `scripts/validate_modules_bulk.py` includes continuity failures in aggregate report.

## Skill Alignment

Update developer skill contracts to include continuity expectations:

- `.opencode/skills/dev-homebrew-ingest/SKILL.md`
  - continuity normalization stage + sidecar verification requirement
- `.opencode/skills/module-gameplay-audit/SKILL.md`
  - readiness now includes continuity gate when enabled for release profile

## Rollout Plan

### Phase A - Warn-first

- Emit continuity section in sidecar.
- Gate reports warnings for unresolved aliases and optional fields.

### Phase B - Strict required fields

- Missing required continuity keys fail ingest/readiness.
- Unresolved aliases remain warnings unless strict alias mode enabled.

### Phase C - Full strict profile

- Required continuity keys + alias resolution coverage enforced for release audits.

## Risks and Mitigations

- Risk: Legacy modules fail immediately.
  - Mitigation: phased enforcement with warn-first mode.
- Risk: Over-constraining narrative authors.
  - Mitigation: normalize only structural metadata, keep prose freeform.
- Risk: Alias ambiguity causes false failures.
  - Mitigation: fail-open ambiguity in early phases; require explicit mapping later.

## Verification

- Unit tests for continuity audit script.
- Integration tests for ingest sidecar `continuity_contract` payload.
- Readiness script tests for gate pass/fail behavior.
- Smoke tests on three modules:
  - `The_Thornwood_Watch`
  - `The_Pumpkin_Kings_Curse`
  - `Night_of_the_Restless_Dead`
