## Why

The toolkit currently exposes only an AI-first Module Builder prompt, while the Homebrew ingest path lives behind developer CLI, watcher, and skill workflows. We need a direct toolkit entrypoint for Homebrewery markdown imports so facilitators can move source material into NEQ modules without leaving the GUI or relying on the `modules/ingest` watcher.

## What Changes

- Add a toolkit-side Homebrew upload flow that accepts `.md` files only for the first slice.
- Add a direct toolkit backend ingest job path that MUST call the shared `run_ingest_pipeline(...)` entrypoint instead of duplicating watcher logic.
- Add toolkit-visible staged ingest reporting for preflight, dry-run, strict ingest, quarantine, and degraded-success outcomes.
- Preserve the existing concept-based Module Builder flow unchanged for users who still want bare-prompt generation.
- Exclude PDF import, semantic publication probes, and full post-build publication parity from this change.

## Capabilities

### New Capabilities
- `toolkit-homebrew-md-upload`: The toolkit can accept Homebrewery markdown files and invoke the shared ingest pipeline directly from the GUI.
- `toolkit-homebrew-ingest-job-reporting`: The toolkit can expose staged ingest status, quarantine reasons, and final result summaries using a stable GUI-facing job contract.

### Modified Capabilities
- None.

## Impact

- Affected toolkit UI: `web/templates/module_toolkit.html`
- Affected web routes/handlers: toolkit upload/job endpoints or socket handlers in `web/web_interface.py` and/or a new toolkit route module
- Shared ingest pipeline reuse: `scripts/homebrew_ingest_dev.py`, `core/importers/homebrewery_importer.py`
- Operational impact: reduces dependence on `modules/ingest` watcher for toolkit-driven ingest while preserving watcher behavior for developer workflows
- Compatibility: MUST remain backward compatible with single-player runtime and existing toolkit concept-builder flows
