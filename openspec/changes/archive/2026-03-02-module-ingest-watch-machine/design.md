## Context

This change defines a production ingestion machine for markdown adventure sources using a watch folder workflow.

The workflow target is simple for facilitators:

1. Save source file into `modules/ingest/`
2. Server ingests automatically
3. Processed source moves to `modules/ingest/archive/` with result sidecar

The first content profile is Homebrewery/GMBinder-style markdown exports with room-based structure (Birble module).

## Goals / Non-Goals

**Goals:**

- Define deterministic watch-folder ingestion contract.
- Define deterministic markdown parser contract for room-based adventure sources.
- Enforce NEQ sequential IDs and schema validation quarantine gate.
- Define archive audit/traceability outputs.
- Provide builder step prompts with verification gates.

**Non-Goals:**

- Full PDF ingestion implementation.
- Multi-format OCR extraction.
- Automatic campaign stitching of quarantined or invalid modules.

## Architecture Decisions

1. **Watch worker model (MUST)**
   - Use one daemon polling worker for `modules/ingest/`.
   - Require file stability (unchanged size/mtime across at least one poll) before ingest.
   - Ignore `modules/ingest/archive/` during scans.

2. **File lifecycle model (MUST)**
   - Every processed source file is moved to `modules/ingest/archive/`.
   - Archive filename includes timestamp and status token (`success`, `quarantined`, `error`).
   - Write sidecar `*.result.json` next to archived source.

3. **Parser model (MUST)**
   - Deterministic text cleaning removes presentation markup (`css`, `<style>`, page macros).
   - Parse semantic headings, room blocks, subsections, and markdown tables.
   - Build normalized intermediate structure before emission.

4. **ID mapping model (MUST)**
   - Generated NEQ IDs are sequential and deterministic (`AREA`, `LOCATION` IDs).
   - Source room numbering (including `Room 100`) is preserved in location display name/metadata only.

5. **Validation gate (MUST)**
   - Run schema validation for emitted module artifacts.
   - Strict mode quarantines invalid output and reports detailed failures.

6. **LLM usage boundary (SHOULD)**
   - Deterministic parse and ID assignment are never delegated to LLM.
   - LLM may enrich sparse narrative fields only after deterministic scaffold exists.

7. **Startup resilience (MUST)**
   - Web startup remains non-blocking if watcher initialization fails.
   - Ingest subsystem failures log warnings/errors and do not crash gameplay server.

## Risks / Trade-offs

- **Risk:** Polling worker ingests partially written files.
  - **Mitigation:** stability gate with unchanged file signature over one poll cycle.

- **Risk:** Content profile drift across markdown sources.
  - **Mitigation:** parser profile pattern (`room-based v1`) + explicit unsupported-pattern warnings.

- **Risk:** Generator output fails schema validation for edge sources.
  - **Mitigation:** strict quarantine and sidecar error report, no silent publish.

- **Risk:** Startup dependency chain failures.
  - **Mitigation:** lazy importer loading in worker processing path.

## Migration Plan

1. Finalize watcher contract and startup integration in `web/extensions/module_ingest_watch.py` and `web/web_interface.py`.
2. Implement deterministic parser internals in `core/importers/homebrewery_importer.py`.
3. Add deterministic NEQ scaffold emission and strict validator integration.
4. Add CLI path `scripts/import_homebrewery_module.py` with dry-run support.
5. Add ingest and parser tests.
6. Validate Birble source ingest end-to-end.
7. Prepare parser-profile extension hooks for additional markdown modules.

Rollback:

- Disable ingest watch by config (`ENABLE_MODULE_INGEST_WATCH = False`).
- Keep manual CLI ingest for debugging.
- Keep all changes additive and extension-first so host code can continue without watcher.

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile core/importers/homebrewery_importer.py web/extensions/module_ingest_watch.py web/web_interface.py model_config.py`
- Worker tests:
  - archive move behavior
  - sidecar payload generation
  - stability-gate deferral
- Parser tests:
  - room extraction coverage
  - subsection and table extraction
  - sequential ID determinism
- Validation tests:
  - strict quarantine on schema failure
  - success path includes artifact list
- Manual smoke:
  - drop source file into `modules/ingest/`
  - verify archive + sidecar
  - verify generated module appears and validates
