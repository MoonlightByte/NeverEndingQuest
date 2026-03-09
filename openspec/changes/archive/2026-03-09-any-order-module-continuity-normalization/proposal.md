## Why

Cross-module narrative links currently exist in uneven, module-specific shapes. `Night_of_the_Restless_Dead` already carries structured cross-module metadata, while `The_Pumpkin_Kings_Curse` and `The_Thornwood_Watch` are mostly standalone with lore-only overlap. This makes "play modules in any order" hard to validate and brittle for future homebrew ingest.

We need a single, additive continuity contract that supports:
- standalone module play,
- campaign-trajectory play,
- and deterministic ingest/validation for new homebrew content.

## What Changes

- Define **Continuity Contract v1** for module-level cross-module metadata and branch outcomes.
- Add ingest-time normalization so homebrew modules are coerced into canonical continuity keys before publish.
- Add readiness validation gate for continuity contract compliance.
- Update developer skills so ingest and module readiness workflows include continuity expectations.
- Keep all changes additive and backward compatible with existing module JSON contracts.

### Non-goals

- No forced rewrite of all existing module prose.
- No mandatory database migration for v2 world narrative in this change.
- No hard requirement that every module must deeply interlock with every other module.

## Capabilities

### New Capabilities
- `module-continuity-contract-v1`: Canonical, additive continuity metadata schema for any-order module play.
- `homebrew-ingest-continuity-normalization`: Ingest pipeline normalization and sidecar reporting for continuity fields.
- `module-readiness-continuity-gate`: Readiness audit gate validating continuity contract compliance.

### Modified Capabilities
- `dev-homebrew-ingest` skill guidance (developer flow contract updated).
- `module-gameplay-audit` skill guidance (readiness gate contract updated).

## Impact

- Affected code (planned implementation scope):
  - `scripts/homebrew_ingest_dev.py`
  - `scripts/homebrew_sidecar_audit.py`
  - `scripts/audit_module_readiness.py`
  - `scripts/validate_modules_bulk.py`
  - `scripts/module_continuity_audit.py` (new)
  - `.opencode/skills/dev-homebrew-ingest/SKILL.md`
  - `.opencode/skills/module-gameplay-audit/SKILL.md`
- Affected content contract:
  - Module continuity keys in `module_context.json` and `module_plot.json`.
- Rollout risk:
  - Medium (new readiness gate and ingest behavior).
  - Mitigated by phased enforcement (warn-first then fail-closed).
- Compatibility:
  - Existing modules remain valid under phased mode; strict mode can be enabled per pipeline.
