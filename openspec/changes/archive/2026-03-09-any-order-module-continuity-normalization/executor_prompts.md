## Prompt 1 - Continuity Contract v1 Specs

Implement OpenSpec artifacts for continuity contract requirements only.

Scope:
- `openspec/changes/any-order-module-continuity-normalization/specs/module-continuity-contract-v1/spec.md`
- `openspec/changes/any-order-module-continuity-normalization/specs/homebrew-ingest-continuity-normalization/spec.md`
- `openspec/changes/any-order-module-continuity-normalization/specs/module-readiness-continuity-gate/spec.md`

Requirements:
- Add MUST-level requirements for required continuity keys and fallback-safe standalone behavior.
- Add SHOULD-level guidance for alias handling and confidence scoring.
- Include scenarios for cold-start and cross-module-aware play.

Do not implement scripts in this prompt.

## Prompt 2 - Ingest + Sidecar Continuity Wiring

Implement continuity normalization integration in ingest path.

Scope:
- `scripts/homebrew_ingest_dev.py`
- `scripts/homebrew_sidecar_audit.py`

Requirements:
- Add continuity normalization stage payload (`continuity_contract`) to ingest sidecar.
- In strict mode, fail when required continuity fields are missing.
- Keep unresolved alias ambiguity as warning in warn-first mode.
- Preserve existing fail-open behavior for non-critical media stages.

Verification:
- Run targeted tests for ingest and sidecar contracts.
- Provide sample sidecar JSON snippet with continuity section.

## Prompt 3 - Readiness Gate Integration

Implement module continuity gate in readiness scripts.

Scope:
- `scripts/module_continuity_audit.py` (new)
- `scripts/audit_module_readiness.py`
- `scripts/validate_modules_bulk.py`

Requirements:
- `module_continuity_audit.py` returns JSON with `blocking_errors`, `warnings`, `required_keys_present`, and exit code 0/1.
- `audit_module_readiness.py` includes continuity gate in strict contract.
- Bulk validator reports continuity pass/fail summary.

Verification:
- Test pass/fail on three modules:
  - `The_Thornwood_Watch`
  - `The_Pumpkin_Kings_Curse`
  - `Night_of_the_Restless_Dead`

## Prompt 4 - Skill and Workflow Contract Updates

Update skill docs so developer workflows include continuity checks.

Scope:
- `.opencode/skills/dev-homebrew-ingest/SKILL.md`
- `.opencode/skills/module-gameplay-audit/SKILL.md`

Requirements:
- Ingest skill documents continuity normalization and sidecar continuity verification.
- Gameplay audit skill documents continuity gate as required in strict readiness profile.
- Keep command examples aligned with implemented script flags.

Verification:
- Read skill docs and confirm command examples are executable and contract-consistent.
