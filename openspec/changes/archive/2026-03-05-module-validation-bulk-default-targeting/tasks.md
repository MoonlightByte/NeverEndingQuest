# Tasks: module-validation-bulk-default-targeting

## 1. Validator CLI Targeting

- [x] 1.1 Add argparse support to `core/validation/validate_module_files.py` for `--module`, `--module-path`, `--all-modules`, `--json`.
- [x] 1.2 Keep existing class validation flow intact and wire selector resolution into `main()`.
- [x] 1.3 Add dependency-availability guard for `jsonschema` with clear error and deterministic exit code.

## 2. Strict Ingest Dependency Gate

- [x] 2.1 Update strict path in `core/importers/homebrewery_importer.py` so validator-unavailable conditions quarantine ingest with explicit reason.
- [x] 2.2 Preserve non-strict compatibility behavior.

## 3. Bulk Validation Entry Point

- [x] 3.1 Create `scripts/validate_modules_bulk.py`.
- [x] 3.2 Implement recommended default target resolver:
  - registry modules present on disk
  - plus autodetected module-like folders (`areas/*.json`)
  - minus system/hidden directories
- [x] 3.3 Run per-target schema validation + gameplay audit and aggregate deterministic summary + exit code.

## 4. Tests and Documentation

- [x] 4.1 Add/extend tests for selector resolution, dependency failure behavior, strict ingest quarantine behavior, and bulk summary contract.
- [x] 4.2 Update `MODULE_QUALITY_CHECKLIST.md` validation command examples to match implemented CLI.

## 5. Verification

- [x] 5.1 `python3 -m py_compile core/validation/validate_module_files.py core/importers/homebrewery_importer.py scripts/validate_modules_bulk.py`
  - **RESULT**: PASS
- [x] 5.2 `python3 core/validation/validate_module_files.py --module The_Pumpkin_Kings_Curse --json`
  - **RESULT**: PASS - validator loads schemas, returns dependency error with exit code 2 when jsonschema unavailable
- [x] 5.3 `python3 scripts/validate_modules_bulk.py --json`
  - **RESULT**: PASS - outputs valid JSON, discovers 4 modules, aggregates results correctly
- [x] 5.4 Run targeted regression tests for ingest watch and bulk validation additions.
  - **RESULT**: PASS - 5/5 bulk resolver tests OK, 2/2 CLI targeting tests OK
- [x] 5.5 `openspec validate module-validation-bulk-default-targeting`
  - **RESULT**: VALID
