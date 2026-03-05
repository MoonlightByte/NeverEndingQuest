# Design: module-validation-bulk-default-targeting

## Context

The repository already has strong ingest pipeline checks, but schema validation ergonomics and dependency behavior leave gaps:
- Per-module schema validation is not directly targetable from CLI.
- Strict ingest should not pass when validator dependencies are unavailable.
- Operators need one deterministic bulk validation command with sane defaults for mixed sources (ingest + GitHub downloads).

## Goals

- Provide deterministic CLI targeting for schema validation.
- Provide deterministic default module target resolution for bulk validation.
- Make strict ingest fail-closed when validator stack is unavailable.
- Keep additive, merge-safe changes with minimal disruption.

## Non-Goals

- Rewriting validation semantics inside `ModuleValidator`.
- Changing watcher polling architecture.
- Replacing gameplay parity audit logic.

## Decisions

### 1) Validator CLI Contract

MUST:
- Add argparse contract in `core/validation/validate_module_files.py` supporting:
  - `--module <slug>`
  - `--module-path <path>`
  - `--all-modules`
  - `--json`
- Ensure help output works even if `jsonschema` is missing.
- Return a clear dependency error message and non-zero exit when validation is requested but `jsonschema` is unavailable.

SHOULD:
- Preserve compatibility behavior when no selector flags are passed (validate current default target).
- Keep existing printed report format unless `--json` is requested.

### 2) Bulk Default Target Resolver

MUST:
- Add a bulk script (`scripts/validate_modules_bulk.py`) that resolves default targets as:
  1) Registered modules from `modules/world_registry.json` that exist on disk.
  2) Module-like directories in `modules/` containing `areas/*.json`.
- Exclude system/non-module directories by explicit denylist and hidden directories.
- De-duplicate and sort target module list deterministically.

SHOULD:
- Expose explicit selectors (`--module`, `--all`, optional include/exclude controls) so operators can override defaults.
- Emit structured summary output for automation (`--json`).

### 3) Strict Ingest Dependency Gate

MUST:
- In strict ingest mode, quarantine when validator dependencies are unavailable.
- Use explicit quarantine reason (`validator_unavailable` or equivalent deterministic reason).
- Avoid pass-default schema success in strict mode when validator cannot run.

SHOULD:
- Keep fail-open behavior in non-strict mode if current flow expects it.

### 4) Exit-Code and Report Contract

MUST:
- Use deterministic exit codes:
  - `0` all selected modules pass schema+audit gates.
  - non-zero if any module has blocking/schema failures or execution errors.

SHOULD:
- Include per-module status sections and final totals.

## Risks and Mitigations

- Risk: false positives from autodiscovery.
  - Mitigation: tight module-like detector (`areas/*.json`) and denylist.
- Risk: operator confusion around new selectors.
  - Mitigation: clear `--help` text and checklist docs update.
- Risk: CI/local mismatch from missing dependencies.
  - Mitigation: explicit dependency errors and predictable exit codes.

## Verification Strategy

- Compile checks for changed Python files.
- Unit tests for target resolver and dependency-failure paths.
- Smoke runs for:
  - one module (`The_Pumpkin_Kings_Curse`)
  - bulk default mode.
- `openspec validate module-validation-bulk-default-targeting`.
