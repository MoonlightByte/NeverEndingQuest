## 1. Continuity Contract v1 (Spec + Shape)

- [x] 1.1 Add continuity v1 requirements and scenarios under `specs/module-continuity-contract-v1/spec.md`
- [x] 1.2 Define required vs optional keys and phase-enforcement rules (warn-first -> strict)
- [x] 1.3 Document canonical key names and alias resolution expectations

## 2. Ingest Normalization Integration

- [x] 2.1 Add continuity normalization stage to `scripts/homebrew_ingest_dev.py`
- [x] 2.2 Emit `continuity_contract` stage payload in ingest sidecar output
- [x] 2.3 Add strict-mode fail criteria for missing required continuity keys
- [x] 2.4 Preserve fail-open handling for unresolved alias ambiguity in warn-first mode

## 3. Continuity Audit Script

- [x] 3.1 Add `scripts/module_continuity_audit.py` for per-module continuity checks
- [x] 3.2 Support JSON output with blocking errors vs warnings
- [x] 3.3 Add strict flag to escalate missing required keys to blockers

## 4. Readiness/Bulk Validation Wiring

- [x] 4.1 Update `scripts/audit_module_readiness.py` to include continuity gate
- [x] 4.2 Update `scripts/homebrew_sidecar_audit.py` to validate continuity payload section when present
- [x] 4.3 Update `scripts/validate_modules_bulk.py` summary to report continuity gate outcomes

## 5. Skill Contract Alignment

- [x] 5.1 Update `.opencode/skills/dev-homebrew-ingest/SKILL.md` continuity stage requirements
- [x] 5.2 Update `.opencode/skills/module-gameplay-audit/SKILL.md` continuity gate in strict readiness contract

## 6. Tests and Verification

- [x] 6.1 Add tests for `module_continuity_audit.py`
- [x] 6.2 Add ingest sidecar tests for continuity payload presence/shape
- [x] 6.3 Add readiness validator tests for continuity pass/fail behavior
- [x] 6.4 Run targeted verification on Thornwood, Pumpkin, and Restless Dead modules
