# toolkit-module-builder-progress-feedback

## Why

During confirmed existing-module rebuilds, the toolkit currently reports that rebuild preparation completed and then appears visually stalled while packet-driven module generation runs. The browser keeps polling the job endpoint, but the backend leaves the job in the `rebuild_clean_running` state until `ModuleBuilder.build_module(...)` returns.

This is misleading during long builds: stdout continues to show real module-builder milestones, but the GUI feedback window can remain frozen for many minutes on `Rebuild preparation complete. Continuing packet build.` The user needs intermittent real progress feedback in the same toolkit console without changing the underlying build pipeline.

## What Changes

### Modified Capabilities

- `toolkit-homebrew-ingest-job-reporting` SHALL expose live packet-build progress milestones while a toolkit-triggered module build is running.
- `toolkit-homebrew-ingest-job-reporting` SHALL preserve rebuild backup and clean-preparation metadata after the handoff into packet build progress.
- `toolkit-homebrew-ingest-job-reporting` SHALL let the GUI render a fresh progress message during long ModuleBuilder execution instead of repeatedly showing only the stale rebuild-clean result.

## Capability Scope

### MUST

- The implementation MUST report real ModuleBuilder progress signals derived from existing builder milestones or logs, not fabricated completion percentages.
- The backend MUST update the existing toolkit job record during long packet builds with a current progress message and timestamp.
- Rebuild-mode jobs MUST transition visibly from rebuild preparation into active packet build progress while preserving backup path/result metadata.
- The frontend MUST display the latest progress message for active build states and continue showing structured job details for troubleshooting.
- The change MUST be fail-open: if progress callback wiring fails, the packet build MUST continue and the existing final success/failure reporting MUST remain intact.
- The change MUST remain ASCII-only in Python user-facing strings.

### SHOULD

- Progress updates should reuse `ModuleBuilder.log(...)` or existing `progress_callback` milestones so GUI feedback matches stdout as closely as practical.
- Progress updates should include a monotonic tick or timestamp so the polling frontend can show that the job is still alive.
- The frontend should avoid excessive visual churn while still surfacing new milestones promptly.

## Non-Goals

- No redesign of the Module Builder pipeline.
- No provider-specific progress streaming from LLM APIs.
- No synthetic percent-complete estimates.
- No change to final readiness, publishability, finisher, or module publication gates.
- No change to overwrite confirmation, backup, or clean rebuild semantics.

## Impact

- Affected code:
  - `web/routes/toolkit_homebrew_routes.py`
  - `web/extensions/toolkit_homebrew_packet_builder.py`
  - `core/generators/module_builder.py` only if needed for minimal callback exposure
  - `web/templates/module_toolkit.html`
  - targeted regression tests under `scripts/`
- Affected workflows:
  - toolkit Homebrew upload jobs
  - confirmed existing-module rebuilds
  - packet-driven Module Builder jobs

## Risks

- Wrapping builder logging incorrectly could hide or duplicate stdout messages.
- Updating job state too aggressively could overwrite meaningful rebuild metadata or final result fields.
- Frontend rendering changes could make structured JSON details less useful if the progress message replaces them entirely.

## Fallback

- If progress callback installation fails, continue the packet build with existing behavior and log a degraded progress state.
- If an active progress update cannot be written to the in-memory job store, continue the build and rely on final job completion reporting.
- If the frontend receives no progress fields, retain the current generic active-build messages.

## Compatibility

- Merge-safety impact is limited to toolkit extension and template surfaces; no tabletop combat/runtime behavior is affected.
- SP/MP gameplay compatibility is unaffected because this change only touches module-toolkit build reporting.
- Provider outage or quota behavior is unchanged; the fix reports local build milestones and does not alter LLM call routing or retry policy.
