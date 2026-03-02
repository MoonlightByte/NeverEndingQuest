## Why

The current ingest machine can produce module artifacts, but a successful ingest is not automatically playable in toolkit flows unless the module is also registered in `modules/world_registry.json`.

Recent ingest behavior also showed markdown watch-file processing entering the AI builder path and producing quarantined output. For tester workflows, we need deterministic markdown ingest and immediate registry registration after strict validation passes.

## What Changes

- Add post-validation registry integration to importer success path.
- Make watch-folder markdown ingest deterministic by default.
- Tighten success contract: success requires both schema pass and registry presence.
- Extend archive sidecar payload with registration audit details.

### MUST Contract

- MUST register module into `world_registry.json` after strict validation passes.
- MUST treat ingest as `success` only when registry presence is confirmed.
- MUST return `quarantined` when strict validation fails or registry integration fails.
- MUST keep `modules/ingest/` watcher on deterministic parser path for `.md`, `.markdown`, `.txt` sources.
- MUST write registration audit fields to sidecar result (`registration_attempted`, `registration_success`, `registry_module_present`, `registration_errors`).
- MUST preserve existing fail-open server startup behavior.

### SHOULD Guidance

- SHOULD use `ModuleStitcher.integrate_module(module_name)` as canonical registration path.
- SHOULD keep importer and watcher changes additive and extension-first.
- SHOULD keep logs clear with `MODULE_INGEST` prefix and explicit registration status.
- SHOULD keep strict mode fail-closed for publishability.

### Non-goals

- No full PDF ingest implementation in this change.
- No EPUB ingestion in this change.
- No redesign of module stitcher internals.
- No auto-stitch/publish of quarantined output.

## Capabilities

### New Capabilities

- `ingest-playable-registration`
- `ingest-deterministic-watch-default`
- `ingest-registration-audit-sidecar`

### Modified Capabilities

- `module-ingest-watch-folder-automation`
- `homebrew-md-sequential-module-ingest`
- `module-ingest-archive-audit-traceability`

## Impact

- Affected files (planned):
  - `core/importers/homebrewery_importer.py`
  - `web/extensions/module_ingest_watch.py`
  - `scripts/test_homebrewery_importer.py`
  - `scripts/test_module_ingest_watch.py`
  - `openspec/changes/module-ingest-playable-registration/*`

- Risk: Medium (registration coupling and stricter success criteria).

- Fallback:
  - Quarantine + archive on registration failure.
  - Keep CLI manual ingest for diagnosis.
  - Keep watcher startup fail-open.
