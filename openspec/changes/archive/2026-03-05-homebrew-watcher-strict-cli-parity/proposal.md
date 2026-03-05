## Why

Watcher ingest is currently not parity with the dev ingest skill pipeline. It directly calls deterministic importer logic, which is fragile for raw Homebrew markdown and can diverge from validated CLI outcomes.

For library operations, we want a strict and predictable workflow:
- Authors/operators produce ingest-ready markdown via the validated dev skill flow.
- Staff/colleagues only need to copy validated files into `modules/ingest/` and start the server.
- Watcher must run a strict ingest path with deterministic outcomes and sidecar evidence.

## What Changes

- Add strict watcher gate: watcher accepts only ingest-ready markdown (no auto-transform in watcher mode).
- Make watcher call the same shared ingest pipeline used by `scripts/homebrew_ingest_dev.py` from validated-input stage onward.
- Keep provider generation opt-in only for prewarm/media stages.
- Ensure watcher sidecar output is complete and audit-compatible for every processed file.
- Add regression tests proving watcher/CLI parity on validated markdown and strict quarantine behavior for non-ready markdown.

## Capabilities

- New: `homebrew-ingest-watch-strict-mode`
- New: `homebrew-ingest-watch-cli-parity`

## Impact

### Affected Code
- `web/extensions/module_ingest_watch.py`
- `scripts/homebrew_ingest_dev.py`
- `scripts/homebrew_preflight.py` (read-only use for strict readiness gate)
- `scripts/test_module_ingest_watch.py`
- `scripts/test_homebrew_ingest_media_pipeline.py` (if parity assertions are added)

### Operational Impact
- Watcher becomes deterministic for validated inputs and explicitly quarantines non-ready inputs.
- Sidecar audit can be relied on for watcher-ingested modules.
- Library onboarding UX improves: validated markdown drop-in workflow.

### Risk / Mitigation
- Risk: overly strict gate rejects borderline files.
  - Mitigation: clear sidecar error reasons and quarantine naming conventions.
- Risk: watcher and CLI drift again.
  - Mitigation: shared pipeline entrypoint and parity tests against same input fixture.

### Compatibility
- Existing validated ingest-ready markdown remains supported.
- Raw/unvalidated markdown is intentionally rejected in strict watcher mode.
