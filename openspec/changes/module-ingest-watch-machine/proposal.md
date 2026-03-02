## Why

We need a builder-ready ingestion machine so facilitators can drop adventure source files into a dedicated watch folder and let the server ingest automatically.

The first production target is:

- `Docs/CLONE - Adventure - Birble Tinkertop's Tinkertop Adventuring Academy.txt`

This source is structured enough to prove deterministic markdown ingest (rooms, subsections, tables, finale), then expand to same-family markdown modules, then start PDF ingestion groundwork.

## What Changes

- Add watch-folder automation contract:
  - watch input folder: `modules/ingest/`
  - archive output folder: `modules/ingest/archive/`
  - poll-based worker with file-stability guard
- Add deterministic Homebrew markdown parser and normalized intermediate model.
- Add NEQ scaffold emission contract with sequential IDs.
- Add strict validation gate and quarantine behavior.
- Add archive traceability contract with sidecar result payload.
- Add builder execution prompts for stepwise implementation and verification.

### MUST Contract

- MUST watch `modules/ingest/` for supported source files (`.md`, `.markdown`, `.txt`).
- MUST move processed source files to `modules/ingest/archive/`.
- MUST write per-file result sidecar JSON with status and validation result.
- MUST enforce NEQ sequential location IDs in generated modules.
- MUST preserve source room labels/numbers in names or metadata only, not as canonical IDs.
- MUST run strict schema validation and quarantine invalid output.
- MUST keep server startup fail-open if watcher initialization fails.
- MUST keep implementation extension-first and merge-safe.

### SHOULD Guidance

- SHOULD keep parser deterministic and use LLM only for bounded enrichment.
- SHOULD provide stable, deterministic output for identical source inputs.
- SHOULD keep logs structured with `MODULE_INGEST` prefixes for ops visibility.
- SHOULD include dry-run mode and targeted regression tests.

### Non-goals

- No EPUB support in this change.
- No full PDF ingest implementation in this change (foundation planning only).
- No auto-stitch into live campaigns before schema-valid output passes quarantine gate.
- No rewrite of existing module builder architecture.

## Capabilities

### New Capabilities

- `module-ingest-watch-folder-automation`
- `homebrew-md-sequential-module-ingest`
- `module-ingest-archive-audit-traceability`

### Modified Capabilities

- None.

## Impact

- Affected code (planned):
  - `core/importers/homebrewery_importer.py`
  - `core/importers/__init__.py`
  - `web/extensions/module_ingest_watch.py`
  - `web/web_interface.py`
  - `model_config.py`
  - `scripts/import_homebrewery_module.py` (new)
  - `scripts/test_module_ingest_watch.py` (new)
  - `scripts/test_homebrewery_importer.py` (new)
  - `plans/ingest-module.md`
- Rollout risk: Medium (background worker + generator/validation path coupling).
- Fallback strategy:
  - Disable watcher by config flag if stability issues appear.
  - Preserve manual CLI ingest path.
  - Keep startup non-blocking if ingest extension fails.
