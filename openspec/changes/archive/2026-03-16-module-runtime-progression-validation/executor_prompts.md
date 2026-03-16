# Executor Prompts: module-runtime-progression-validation

## Execution Contract

MUST:
- Implement only the scoped validator and test work described by this change.
- Keep runtime behavior unchanged; this slice is validation-only unless a narrow reusable graph helper is required.
- Preserve existing CLI selectors and dependency-failure behavior.
- Keep all Python log and operator output ASCII-only.
- Use additive, anchored patches; do not broad-rewrite `core/validation/validate_module_files.py`.
- Run `python3 -m py_compile <changed_python_file>` after each touched Python file.
- Stop and report if an existing spec or validator contract makes one of the new checks ambiguous.

SHOULD:
- Reuse current runtime graph semantics instead of inventing a second graph model.
- Prefer small helper extraction for graph checks over deeply nested inline logic.
- Keep deterministic checks limited to explicit authored graph/progression data.

## Prompt 1 - Contract Tests First (Tasks 1.1-1.4)

Implement the contract/regression tests before changing validator behavior.

Scope:
- Add targeted tests that prove:
  1. Human-report and `--json` CLI paths both execute the same full validation suite.
  2. A single-area module with missing `locations[*].connectivity` fails runtime reachability validation.
  3. A map/area room-graph mismatch fails parity validation.
  4. Unreachable plot locations, broken branch `path`/`bypass` steps, and ungated conclusion beats fail deterministically.
- Keep fixtures minimal and isolated; prefer temp dirs or focused sample module payloads.
- Do not change production validator behavior in this prompt except the minimum required test hooks.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run the new tests and confirm they fail for the missing implementation reasons, not syntax/setup reasons.

## Prompt 2 - Canonical CLI Validation Path (Tasks 2.1-2.2)

Unify validator execution so all CLI output modes run the same full suite.

Scope:
- Refactor `core/validation/validate_module_files.py` so both human-readable and JSON output use one canonical full-validation method.
- Ensure the path includes existing checks plus the connectivity/progression hooks that currently drift.
- Preserve selector resolution, exit-code behavior, and `jsonschema` dependency messaging.
- Keep report formatting differences separate from validation execution.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification before continuing:
- `python3 -m py_compile core/validation/validate_module_files.py`
- Run one module validation with and without `--json` and confirm both paths populate the same result domains.

## Prompt 3 - Runtime Room Reachability + Map Parity (Tasks 3.1-3.2)

Add deterministic graph validation for room traversal and map parity.

Scope:
- In `core/validation/validate_module_files.py`, implement:
  - intra-area room reachability validation using runtime `locations[*].connectivity`
  - room-graph parity validation comparing `areas/*.json` room edges with `map_*.json` room edges
- Fail closed on explicit graph contradictions only.
- Emit diagnostics with room IDs and file context.
- Do not mutate module files during validation.

Constraints:
- Runtime `connectivity` is the authoritative traversal source.
- Map files are parity artifacts, not the primary source of truth.
- Single-area modules MUST be covered.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification before continuing:
- `python3 -m py_compile core/validation/validate_module_files.py`
- Run the new graph-focused tests.

## Prompt 4 - Plot Progression Path Validation (Task 3.3-3.4)

Add deterministic progression validation tied to the authored room graph.

Scope:
- Validate module starting location reachability to each `plotPoints[*].location`.
- Validate explicit branch metadata arrays such as `path` and `bypass` when present.
- Add deterministic conclusion/finale gate checks when upstream progression clearly exists but explicit prerequisites are missing.
- Diagnostics MUST include plot IDs, room IDs, and reason text for surgical fixes.

Constraints:
- Use only explicit authored metadata.
- Ignore prose-only hints and ambiguous narrative descriptions.
- Preserve fail-open behavior for metadata that is not machine-checkable.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification before continuing:
- `python3 -m py_compile core/validation/validate_module_files.py`
- Run the progression-focused tests and ensure explicit failures are deterministic.

## Prompt 5 - Final Verification (Tasks 4.1-4.5)

Run final verification and provide a concise report.

Required checks:
- `python3 -m py_compile core/validation/validate_module_files.py <changed_test_files>`
- Run targeted validator regression tests added in this change
- `python3 core/validation/validate_module_files.py --module Night_of_the_Restless_Dead`
- `python3 core/validation/validate_module_files.py --module The_Pumpkin_Kings_Curse`
- `openspec validate module-runtime-progression-validation`

Report format:
- Files changed
- Commands run
- PASS/FAIL per verification gate
- Any remaining follow-up or contract ambiguity
