## Overview

Phase 7 completes the upload pipeline by making artifacts visible, rebuilds resumable, and failed uploads cleanable. All Phase 7 changes are additive to the existing uploader orchestration.

## Goals

- MUST expose explicit artifact manifests in job status responses.
- MUST add retry-from-packet route that reruns build without re-running normalization.
- MUST add retry-from-finishing route that reruns finisher without re-running build.
- MUST preserve all existing state machine transitions and validation gates.
- MUST reuse existing rebuild guard for repeated upload rebuilds.
- SHOULD display artifact summary links in toolkit UI as read-only diagnostics.
- SHOULD add job cleanup route for abandoned failed uploads.
- SHOULD persist all artifacts until explicit cleanup.

## Non-Goals

- Do not add automatic cleanup triggers.
- Do not add automatic rebuild orchestration beyond explicit retry routes.
- Do not modify existing job state transitions or validation logic.
- Do not change the normalization or readiness repair contracts.
- Do not add inline artifact editing.

## Architecture

### Artifact Manifest Contract

Job status responses MUST include an `artifact_manifest` field:

```json
{
  "artifact_manifest": {
    "workspace": "/path/to/workspace",
    "artifacts": {
      "source_original": { "exists": true, "path": "...", "size_bytes": N },
      "normalized_packet": { "exists": true, "path": "...", "size_bytes": N },
      "normalization_report": { "exists": true, "path": "...", "size_bytes": N },
      "ui_review_snapshot": { "exists": false },
      "builder_input": { "exists": true, "path": "...", "size_bytes": N },
      "build_result": { "exists": true, "path": "...", "size_bytes": N },
      "readiness_validation_report": { "exists": false },
      "readiness_audit_report": { "exists": false },
      "repair_report": { "exists": false },
      "finishing_report": { "exists": false }
    },
    "rebuild_eligible": {
      "from_packet": true,
      "from_finishing": false
    },
    "cleanup_allowed": true
  }
}
```

### Rebuild Eligibility Rules

A job is eligible for `retry-from-packet` when:
1. `normalized_packet` artifact exists,
2. job status is terminal (`completed`, `not_publishable`, `quarantined`, `failed`) OR user explicitly requests retry,
3. no conflicting active job is running.

A job is eligible for `retry-from-finishing` when:
1. `builder_input` and `build_result` artifacts exist,
2. job has previously reached `ready_for_finishing` or `finishing`,
3. `finishing_report` does not yet exist or user explicitly requests retry,
4. no conflicting active job is running.

### Retry Routes

Two new route handlers:

1. `POST /api/homebrew/retry-from-packet` — skips normalization, runs build from existing packet, then continues through finishing.
2. `POST /api/homebrew/retry-from-finishing` — skips build, runs finishing from existing build artifacts.

Both routes:
- validate artifact existence before proceeding,
- use existing rebuild guard to prevent concurrent job conflicts,
- return the same job status response as a normal build/finish progression.

### Cleanup Route

One new route handler:

`POST /api/homebrew/cleanup` — removes upload workspace directory and all artifacts for a given job. Fails if job is not in a terminal state unless `force=true`.

### Frontend Visibility

The toolkit UI SHOULD show:
- read-only artifact list per job (file names and sizes, not raw content),
- rebuild buttons enabled only when eligibility conditions are met,
- cleanup button available for terminal-state jobs.
