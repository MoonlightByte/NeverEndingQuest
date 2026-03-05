## 1. Monster Reference Integrity Validator

- [x] 1.1 Add monster-name normalization helper in `core/validation/validate_module_files.py` aligned with combat lookup semantics.
- [x] 1.2 Add `validate_monster_references()` that scans area/location monster references and verifies `monsters/<slug>.json` exists.
- [x] 1.3 Record failures in a new `reference_integrity` result bucket with area/location/source-name/expected-path details.
- [x] 1.4 Wire `validate_monster_references()` into `run_all_validations()` and `print_report()` ordering.

## 2. Ingest and Activation Gate Enforcement

- [x] 2.1 Ensure importer strict validation surfaces `reference_integrity` failures in returned `validation.errors` and quarantines accordingly.
- [x] 2.2 Ensure ingest watcher strict path continues to fail/quarantine on new validator failures (no bypass).
- [x] 2.3 Add module activation/copy preflight validator hook; block activation when unresolved monster references exist.
- [x] 2.4 Emit concise `[SYSTEM]` preflight failure summary for blocked activation/copy with pointer to detailed logs/sidecar.

## 3. Runtime Failure Surfacing and Narration Gate

- [x] 3.1 Enrich `createEncounter` error message in `core/ai/action_handler.py` with missing monster/stat-file context when available from builder output.
- [x] 3.2 Preserve existing system-message append path in `main.py` and ensure enriched message reaches chat as `[SYSTEM]`.
- [x] 3.3 Prevent combat narration emission when the same turn includes `createEncounter` and that action returns `status:error`.
- [x] 3.4 Keep narration behavior unchanged for turns without failed `createEncounter`.

## 4. Regression Coverage

- [x] 4.1 Add validator tests for unresolved monster refs, valid refs, and normalization edge cases.
- [x] 4.2 Add ingest/strict-path regression test showing unresolved refs produce quarantined status.
- [x] 4.3 Add runtime regression test ensuring failed `createEncounter` yields `[SYSTEM]` message and no combat narration leak.

## 5. Verification

- [x] 5.1 Run `python3 -m py_compile core/validation/validate_module_files.py core/importers/homebrewery_importer.py core/ai/action_handler.py main.py`.
- [x] 5.2 Run targeted validator/runtime regression tests added in this change.
- [x] 5.3 Run `python3 core/validation/validate_module_files.py` (or module-targeted invocation if CLI is expanded) and confirm reference integrity summary appears.
- [x] 5.4 Run `openspec validate tt-combat-encounter-reference-integrity`.
