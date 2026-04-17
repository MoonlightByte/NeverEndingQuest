## Why

The public Homebrew upload path now supports normalization, review, packet-driven build, structural readiness repair, and finisher/publication attachment. Upload jobs can complete through to `completed` or `not_publishable`, and repeated uploads can rebuild cleanly. However, the uploader does not yet expose artifact visibility, rebuild-from-artifact UX, or cleanup policy to operators and developers.

This leaves the uploader opaque:
- operators cannot see which artifacts exist for a completed or failed job without inspecting the filesystem,
- rebuild-from-artifact requires manual route orchestration rather than an explicit retry path,
- failed uploads accumulate indefinitely with no cleanup mechanism.

## What Changes

- Add artifact visibility surface to the upload job status response so the frontend can display which artifacts exist for a given job.
- Add explicit retry-from-packet route that resumes build without rerunning normalization (when the normalized packet still exists).
- Add explicit retry-from-finishing route that resumes finisher without rerunning build (when build artifacts still exist and readiness already passed).
- Add job cleanup route that removes abandoned failed upload workspaces and their artifacts.
- Persist all job artifacts (normalized packet, review snapshot, build input, readiness reports, repair reports, finisher report) in the upload workspace until explicit cleanup.
- MUST reuse the existing rebuild guard already implemented for repeated uploads.
- MUST preserve all existing job state transitions and validation gates.
- SHOULD expose artifact summaries in the toolkit UI as read-only diagnostic links.
- Non-goals: automatic cleanup triggers, automatic rebuild orchestration beyond explicit retry routes.

## Capabilities

### New Capabilities
- `toolkit-homebrew-artifact-visibility`: job status responses include artifact manifest showing which workspace files exist and their persistence state.
- `toolkit-homebrew-rebuild-resume`: explicit route to retry build from normalized packet (skipping normalization) and to retry finishing from build artifacts (skipping build).

### Modified Capabilities
- `toolkit-homebrew-ingest-job-reporting`: job reporting now includes artifact summary and rebuild eligibility indicators alongside existing state/status fields.

## Impact

- Affected upload orchestration: `web/routes/toolkit_homebrew_routes.py`
- Affected toolkit frontend: `web/templates/module_toolkit.html`
- New cleanup helper: `scripts/toolkit_homebrew_cleanup.py`
- Artifact/reporting impact: job status and retry responses now carry explicit artifact manifests.
- Merge-safety impact: additive only; existing routes and state machine unchanged.
- SP/MP compatibility impact: no gameplay runtime change; toolkit-only.
- Rollout risk: low, because all changes are additive and reuse existing infrastructure.
