# Tasks: module-runtime-progression-validation

## 1. Contract Locks and Regression Fixtures

- [x] 1.1 Add validator contract tests that prove the CLI human-report path and `--json` path execute the same validation suite.
- [x] 1.2 Add regression fixtures/tests for intra-area room reachability failures in single-area modules.
- [x] 1.3 Add regression fixtures/tests for area/map room-graph parity drift.
- [x] 1.4 Add regression fixtures/tests for unreachable plot points, broken branch paths, and ungated conclusion beats.

## 2. Canonical Validator Execution Path

- [x] 2.1 Refactor `core/validation/validate_module_files.py` so both CLI output modes route through one canonical full-validation method.
- [x] 2.2 Preserve existing selector behavior (`--module`, `--module-path`, `--all-modules`, `--json`) and existing dependency-failure semantics.

## 3. Runtime Graph Validation Additions

- [x] 3.1 Implement intra-area runtime room reachability validation using the same room-edge semantics consumed by runtime pathing.
- [x] 3.2 Implement area/map room-graph parity validation for matching room IDs.
- [x] 3.3 Implement plot progression path validation for start location, plot point locations, explicit branch metadata paths, and conclusion gating.
- [x] 3.4 Ensure validation diagnostics include file path, room IDs, and plot IDs needed for surgical fixes.

## 4. Verification and Smoke Coverage

- [x] 4.1 `python3 -m py_compile core/validation/validate_module_files.py <new_or_changed_test_files>`
- [x] 4.2 Run targeted validator regression tests for all new graph/progression domains.
- [x] 4.3 Run `python3 core/validation/validate_module_files.py --module Night_of_the_Restless_Dead` and verify the fixed module passes under the expanded suite.
- [x] 4.4 Run at least one healthy comparison module validation smoke (for example `The_Pumpkin_Kings_Curse` or `Keep_of_Doom`) and verify no regression.
- [x] 4.5 `openspec validate module-runtime-progression-validation`

## SHOULD Notes

- SHOULD keep validator edits additive and concentrated in `core/validation/validate_module_files.py` unless a narrow reusable helper materially reduces drift.
- SHOULD avoid schema changes in this slice unless implementation proves a validator contract cannot be expressed against existing authored fields.
