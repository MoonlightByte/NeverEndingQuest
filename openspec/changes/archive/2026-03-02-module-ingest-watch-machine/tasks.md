## 0. Change scaffold and config lock

- [x] 0.1 Create/confirm change scaffold files (`proposal.md`, `design.md`, `tasks.md`, `executor_prompts.md`, capability specs).
- [x] 0.2 Lock watch-folder contract in docs: input `modules/ingest/`, archive `modules/ingest/archive/`.
- [x] 0.3 Lock sequential ID policy for markdown imports (source room numbers are metadata only).

## 1. Watch worker and startup integration

- [x] 1.1 Finalize config constants in `model_config.py` for enable flag, dirs, poll interval, extensions, strict validation.
- [x] 1.2 Finalize watcher worker in `web/extensions/module_ingest_watch.py` with idempotent start/stop and thread-safe stats.
- [x] 1.3 Enforce file-stability gate (unchanged size/mtime over one poll cycle) before ingestion.
- [x] 1.4 Ensure archive folder is excluded from candidate scans.
- [x] 1.5 Wire startup hook in `web/web_interface.py` with fail-open behavior.

## 2. Deterministic markdown parser (Birble profile)

- [x] 2.1 Implement deterministic source cleaning in `core/importers/homebrewery_importer.py` (remove css/style/layout macros).
- [x] 2.2 Implement heading + room block extraction (`## Room N:` pattern).
- [x] 2.3 Implement subsection extraction (`Puzzle`, `Solution`, `Creatures`, exit comments, tables).
- [x] 2.4 Build normalized intermediate adventure object for room-chain profile.

## 3. NEQ scaffold emission and sequential IDs

- [x] 3.1 Emit deterministic module slug + area/location IDs using NEQ sequential policy.
- [x] 3.2 Preserve source room numbers in display labels/metadata only (including outliers like `Room 100`).
- [x] 3.3 Emit module artifacts (`module_context`, `module_plot`, `areas`, `map`) from deterministic templates.
- [x] 3.4 Integrate strict validation check and quarantine return path on schema failure.

## 4. Archive and audit traceability

- [x] 4.1 Move all processed files (success/quarantined/error) into `modules/ingest/archive/`.
- [x] 4.2 Write sidecar `*.result.json` with status, validation summary, artifacts, and errors.
- [x] 4.3 Ensure archive filename collision handling is deterministic and non-destructive.
- [x] 4.4 Add structured logs with `MODULE_INGEST` prefix and per-file status.

## 5. CLI and operator tooling

- [x] 5.1 Add `scripts/import_homebrewery_module.py` for manual/diagnostic ingest.
- [x] 5.2 Add `--dry-run` mode for parse preview without writing module artifacts.
- [x] 5.3 Add clear exit codes and summary output for CI/operator scripting.

## 6. Tests and verification

- [x] 6.1 Add `scripts/test_module_ingest_watch.py` for worker file lifecycle behavior.
- [x] 6.2 Add `scripts/test_homebrewery_importer.py` for parser and sequential ID determinism.
- [x] 6.3 Add strict validation regression checks for quarantine behavior.
- [x] 6.4 Run compile checks on all modified Python files.
- [x] 6.5 Run manual smoke: drop Birble file into `modules/ingest/`, verify archive+sidecar+module output.

## 7. Builder handoff

- [x] 7.1 Keep `openspec/changes/module-ingest-watch-machine/executor_prompts.md` aligned with tasks and file scopes.
- [x] 7.2 Include explicit verification commands and stop conditions in each prompt.
