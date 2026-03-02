## Builder Execution Prompts - module-ingest-watch-machine

## Execution Contract

- MUST implement tasks in order; do not skip verification gates.
- MUST preserve extension-first architecture and minimal host edits.
- MUST keep server startup fail-open if ingest watcher fails.
- MUST enforce NEQ sequential IDs and strict quarantine behavior.
- SHOULD keep parser deterministic and treat LLM as enrichment-only.
- SHOULD keep logs structured with `MODULE_INGEST` for operational visibility.

## Prompt 1 - Lock Watcher Contract and Config (tasks 0.x, 1.1)

Scope:

- `model_config.py`
- `plans/ingest-module.md` (contract alignment only if needed)

Requirements:

- Add/confirm watcher constants:
  - `ENABLE_MODULE_INGEST_WATCH`
  - `MODULE_INGEST_WATCH_DIR`
  - `MODULE_INGEST_ARCHIVE_DIR`
  - `MODULE_INGEST_POLL_INTERVAL_SECONDS`
  - `MODULE_INGEST_ALLOWED_EXTENSIONS`
  - `MODULE_INGEST_STRICT_VALIDATION`
- Keep defaults aligned with contract:
  - watch: `modules/ingest/`
  - archive: `modules/ingest/archive/`
  - strict validation enabled

Verify:

- `python3 -m py_compile model_config.py`

Stop conditions:

- Stop if config syntax fails.
- Stop if constants conflict with watch-folder contract.

## Prompt 2 - Implement Watch Worker Lifecycle (tasks 1.2, 1.3, 1.4)

Scope:

- `web/extensions/module_ingest_watch.py`

Requirements:

- Implement idempotent start/stop worker functions.
- Implement polling loop with:
  - extension filter
  - archive exclusion
  - file-stability guard (size+mtime unchanged over one interval)
- Implement archive move behavior with collision-safe naming.
- Implement per-file sidecar result writing.
- Implement thread-safe runtime stats snapshot API.

Verify:

- `python3 -m py_compile web/extensions/module_ingest_watch.py`
- Add/execute worker-focused tests if available.

Stop conditions:

- Stop if worker can process files before stability guard passes.
- Stop if archive collisions overwrite existing files.

## Prompt 3 - Wire Server Startup Fail-Open (task 1.5)

Scope:

- `web/web_interface.py`

Requirements:

- Import watcher start function safely.
- Start watcher at startup only when enabled.
- Keep import/start exceptions fail-open with warning logs.
- Preserve existing startup flow and TABLETOP MODE boundary comments.

Verify:

- `python3 -m py_compile web/web_interface.py`
- Manual smoke: start server with watcher enabled and disabled.

Stop conditions:

- Stop if watcher failure blocks server startup.

## Prompt 4 - Implement Deterministic Birble Parser (tasks 2.1, 2.2, 2.3, 2.4)

Scope:

- `core/importers/homebrewery_importer.py`

Requirements:

- Implement deterministic cleaning (remove css/style/layout artifacts).
- Implement room extraction (`## Room N:`) in source order.
- Implement subsection extraction (Puzzle, Solution, Creatures, exit comments, tables).
- Build normalized intermediate object for room-chain profile.
- Keep parser deterministic and free of LLM dependency for extraction logic.

Verify:

- `python3 -m py_compile core/importers/homebrewery_importer.py`
- Add/execute importer parser tests (room count/order/subsection extraction).

Stop conditions:

- Stop if parser output changes IDs/order nondeterministically between runs.

## Prompt 5 - Emit Sequential NEQ Artifacts + Validation Gate (tasks 3.1, 3.2, 3.3, 3.4)

Scope:

- `core/importers/homebrewery_importer.py`
- optional helper files under `core/importers/`

Requirements:

- Emit deterministic module artifacts:
  - `module_context.json`
  - `module_plot.json`
  - `areas/<AREA>.json`
  - `map_<AREA>.json`
- Use sequential NEQ area/location IDs only.
- Preserve source room numbers as display labels/metadata only.
- Run strict validation and return `quarantined` on schema failure.

Verify:

- `python3 -m py_compile core/importers/homebrewery_importer.py`
- `python3 core/validation/validate_module_files.py`

Stop conditions:

- Stop if literal source room numbers leak into canonical NEQ IDs.
- Stop if strict mode allows invalid module to pass as success.

## Prompt 6A - Add Operator CLI (tasks 5.1, 5.2, 5.3)

Scope:

- `scripts/import_homebrewery_module.py`

Requirements:

- Implement manual ingest CLI with args:
  - `--source`, `--module-slug`, `--strict/--no-strict`, `--no-llm`, `--dry-run`, `--deterministic`, `--output-root`, `--json`
- Exit codes: 0 (success), 1 (quarantined), 2 (error)
- JSON and human-readable output modes

Verify:

- `python3 -m py_compile scripts/import_homebrewery_module.py`
- `python3 scripts/import_homebrewery_module.py --help`

Stop conditions:

- Stop if CLI lacks required arguments or exit codes.

## Prompt 6A.1 - Harden Dry-Run No-Write Contract

Scope:

- `scripts/import_homebrewery_module.py`
- `core/importers/homebrewery_importer.py`

Requirements:

- Enforce `--dry-run` requires `--deterministic` to guarantee no artifact writes
- Exit code 2 with clear error if user tries `--dry-run` without `--deterministic`
- Both JSON and human-readable error modes

Verify:

- `python3 scripts/import_homebrewery_module.py --source <file> --dry-run --deterministic` (should work)
- `python3 scripts/import_homebrewery_module.py --source <file> --dry-run` (should exit 2)
- Confirm no files written in dry-run cases

Stop conditions:

- Stop if any dry-run path writes artifacts.

## Prompt 6B - Add Ingest Tests (tasks 6.1, 6.2, 6.3, 6.4)

Scope:

- `scripts/test_module_ingest_watch.py`
- `scripts/test_homebrewery_importer.py`

Requirements:

- Worker lifecycle tests: archive move, sidecar write, collision-safe naming
- Importer deterministic tests: room extraction order, sequential ID mapping, Room 100 metadata handling
- Strict quarantine regression checks

Verify:

- `python3 -m py_compile scripts/test_module_ingest_watch.py scripts/test_homebrewery_importer.py`
- `python3 scripts/test_module_ingest_watch.py` (10 tests)
- `python3 scripts/test_homebrewery_importer.py` (21 tests)

Stop conditions:

- Stop if tests fail or are flaky.
- Stop if dry-run writes module artifacts during tests.

## Prompt 7A - Close Archive Traceability + E2E Smoke + Handoff (tasks 4.x, 6.5, 7.x)

Scope:

- `web/extensions/module_ingest_watch.py` (verify behavior)
- `core/importers/homebrewery_importer.py` (verify behavior)
- `openspec/changes/module-ingest-watch-machine/tasks.md`
- `openspec/changes/module-ingest-watch-machine/executor_prompts.md`

Requirements:

1. Complete archive traceability (tasks 4.1-4.4):
   - Verify processed files moved to `modules/ingest/archive/`
   - Verify sidecar `*.result.json` written with status/validation/artifacts
   - Verify collision-safe archive naming
   - Verify structured `MODULE_INGEST` logs present

2. Complete E2E smoke test (task 6.5):
   - Ingest Birble source: `python3 scripts/import_homebrewery_module.py --source "modules/ingest/CLONE..." --module-slug Birble_Adventuring_Academy --deterministic --strict`
   - Verify module created at `modules/Birble_Adventuring_Academy/` with 4 artifacts
   - Verify IDs sequential: BIR001, BIR01-BIR23 (NOT BIR100 for Room 100)
   - Verify source room numbers preserved as metadata only
   - Verify Room 100 -> location ID BIR23 with `source_room_number: 100`

3. Complete builder handoff (tasks 7.1-7.2):
   - Update `tasks.md` marking all tasks complete
   - Update `executor_prompts.md` to reflect actual execution history (include 6A.1 dry-run hardening)

Verify:

- `python3 -m py_compile core/importers/homebrewery_importer.py web/extensions/module_ingest_watch.py scripts/import_homebrewery_module.py`
- `python3 scripts/test_homebrewery_importer.py` (21 tests)
- `python3 scripts/test_module_ingest_watch.py` (10 tests)
- `ls modules/Birble_Adventuring_Academy/` confirms 4 artifacts
- `git status --short`

Stop conditions:

- Stop if module artifacts missing.
- Stop if IDs not sequential.
- Stop if source room numbers leaked into canonical IDs.
- Stop if any tests fail.
