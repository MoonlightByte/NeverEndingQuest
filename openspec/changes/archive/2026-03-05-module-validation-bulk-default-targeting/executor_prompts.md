# Executor Prompts: module-validation-bulk-default-targeting

## Execution Contract

MUST:
- Implement exactly the scoped files and contracts in this change.
- Keep edits additive and merge-safe; preserve existing behavior outside listed contracts.
- Use ASCII-only output in Python logs/messages.
- Run `python3 -m py_compile <changed_python_file>` after each Python file edit.
- Stop and report if an unexpected dependency or environment blocker appears.

SHOULD:
- Keep patches surgical and anchored.
- Prefer extending existing functions over broad refactors.
- Reuse existing scripts (`audit_module_gameplay.py`) instead of duplicating logic.

## Prompt 1 - Validator CLI Targeting (Tasks 1.1-1.3)

Implement argparse targeting in `core/validation/validate_module_files.py`.

Scope:
- Add selector args: `--module`, `--module-path`, `--all-modules`, `--json`.
- Keep `ModuleValidator` internals unchanged unless required for selector wiring.
- Ensure `--help` works even if `jsonschema` is missing.
- Add dependency gate: when validation is requested and `jsonschema` is unavailable, print clear install guidance and exit non-zero.

Verification before continuing:
- `python3 -m py_compile core/validation/validate_module_files.py`
- `python3 core/validation/validate_module_files.py --help`

## Prompt 2 - Strict Ingest Gate (Tasks 2.1-2.2)

Update strict ingest path in `core/importers/homebrewery_importer.py`.

Scope:
- Detect validator-unavailable condition from `_validate_module_artifacts` flow.
- In strict mode, quarantine with deterministic reason (for example `validator_unavailable`).
- Preserve non-strict compatibility behavior.

Verification before continuing:
- `python3 -m py_compile core/importers/homebrewery_importer.py`
- Run/extend targeted ingest tests that assert strict quarantine when validator stack is unavailable.

## Prompt 3 - Bulk Validator with Recommended Default (Tasks 3.1-3.3)

Create `scripts/validate_modules_bulk.py`.

MUST implement recommended default target resolver:
1) Include registry modules from `modules/world_registry.json` when folder exists.
2) Include autodetected module-like directories under `modules/` with `areas/*.json`.
3) Exclude system/non-module directories (`ingest`, `conversation_history`, `campaign_summaries`, `backups`, hidden directories, and similar non-play modules).
4) De-duplicate and sort targets deterministically.

Execution behavior:
- For each target module, run schema validation plus gameplay audit.
- Emit per-module result and aggregate summary.
- Support `--json` for machine-readable output.
- Exit non-zero on any schema failure, blocking audit error, or execution error.

Verification before continuing:
- `python3 -m py_compile scripts/validate_modules_bulk.py`
- `python3 scripts/validate_modules_bulk.py --json`

## Prompt 4 - Tests and Docs (Tasks 4.1-4.2)

Add/extend tests and update docs.

Scope:
- Add tests for:
  - validator selector resolution
  - missing dependency behavior
  - strict ingest validator-unavailable quarantine
  - bulk resolver default inclusion/exclusion logic
- Update `MODULE_QUALITY_CHECKLIST.md` commands to match real CLI usage.

Verification before final:
- Run targeted regression tests touched by this change.

## Prompt 5 - Final Verification (Tasks 5.1-5.5)

Run final checks and provide a concise report:
- compile checks
- module-target smoke (`The_Pumpkin_Kings_Curse`)
- bulk default smoke
- targeted tests
- `openspec validate module-validation-bulk-default-targeting`

Report format:
- Files changed
- Commands run
- PASS/FAIL per gate
- Any follow-up items
