## 1. Post-Build Readiness State Model

- [x] 1.1 Add explicit upload job states for `validating`, `repairing_deterministic`, `repairing_semantic`, and `ready_for_finishing`.
- [x] 1.2 Add explicit bounded failure states such as `build_system_failed` and `repair_budget_exhausted`.
- [x] 1.3 Ensure packet-driven `build_completed` remains distinct from later readiness and completion states.

## 2. Authoritative Readiness Gate

- [x] 2.1 Add a shared readiness-gate orchestrator that runs `core/validation/validate_module_files.py` for packet-built modules.
- [x] 2.2 Extend the orchestrator to run `scripts/audit_module_readiness.py` and persist grouped readiness results to the upload workspace.
- [x] 2.3 Fail closed when builder/runtime defects are detected, without entering content repair loops.

## 3. Deterministic Repair Domains

- [x] 3.1 Add deterministic repair for party/world enum normalization and safe field-shape cleanup.
- [x] 3.2 Add deterministic monster materialization or equivalent monster-reference repair before finisher entry.
- [x] 3.3 Add deterministic spatial-contract repair for coordinates/directions parity when authoritative connectivity is available.
- [x] 3.4 Add deterministic regeneration for derived artifacts such as `module_context.json` and `MODULE_SUMMARY.md`.

## 4. Targeted Semantic Repair

- [x] 4.1 Add a narrow semantic repair path for missing NPC placement using existing generated locations only.
- [x] 4.2 Add a narrow semantic repair path for plot-hook or summary alignment only if deterministic repair leaves those domains unresolved.
- [x] 4.3 Enforce bounded repair budgets and stop conditions when validation signatures do not improve.

## 5. Toolkit Reporting And UX

- [x] 5.1 Update `web/templates/module_toolkit.html` to show readiness-stage progress distinctly from raw build completion.
- [x] 5.2 Add grouped validation/repair reporting to the toolkit status surface and update stale review-panel wording after approval/build start.
- [x] 5.3 Surface `ready_for_finishing` as the first post-build success state that may enter the finisher in the next uploader slice.

## 6. Regression Coverage

- [x] 6.1 Add tests for raw `build_completed` vs `ready_for_finishing` distinction.
- [x] 6.2 Add tests that deterministic repair domains run before semantic repair.
- [x] 6.3 Add tests that builder/runtime defects classify as `build_system_failed` and bypass repair loops.
- [x] 6.4 Add tests that repair budget exhaustion produces inspectable grouped failure artifacts.

## 7. Verification

- [x] 7.1 Run targeted syntax validation for new readiness-gate and upload-route changes.
- [x] 7.2 Run targeted regression tests for readiness-state transitions, deterministic repair ordering, and stop conditions.
- [x] 7.3 Re-run a real packet-built fixture smoke path and confirm the job reaches `ready_for_finishing` or a bounded failure state with preserved artifacts.
- [x] 7.4 Run `openspec validate toolkit-homebrew-structural-readiness-gate`.
