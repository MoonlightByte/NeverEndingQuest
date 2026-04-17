## 1. Artifact Manifest in Job Status

- [x] 1.1 Add `build_artifact_manifest(workspace: Path) -> Dict` helper in `web/routes/toolkit_homebrew_routes.py` that returns the full artifact manifest structure with `exists`, `path`, `size_bytes` per key and the `rebuild_eligible` block.
- [x] 1.2 Wire `build_artifact_manifest` into all job status response points so every GET/status route includes `artifact_manifest` in its top-level response.
- [x] 1.3 Add unit tests for `build_artifact_manifest` covering all artifact keys and both `rebuild_eligible` flag states.

## 2. Retry-From-Packet Route

- [x] 2.1 Add `POST /api/homebrew/retry-from-packet` route handler in `web/routes/toolkit_homebrew_routes.py` that:
  - loads the existing job state,
  - calls `build_artifact_manifest` and validates `normalized_packet` exists,
  - uses existing rebuild guard to check for concurrent active jobs,
  - proceeds to build-from-packet flow (reuse existing build orchestration, skipping normalization).
- [x] 2.2 Return structured error with `reason: "missing_artifacts"` and missing key list when packet is absent.
- [x] 2.3 Return structured error with `reason: "job_already_active"` when rebuild guard rejects.
- [x] 2.4 Add regression tests for retry-from-packet covering success path, missing packet error, and concurrent job rejection.

## 3. Retry-From-Finishing Route

- [x] 3.1 Add `POST /api/homebrew/retry-from-finishing` route handler in `web/routes/toolkit_homebrew_routes.py` that:
  - loads the existing job state,
  - calls `build_artifact_manifest` and validates `builder_input` and `build_result` exist,
  - uses existing rebuild guard to check for concurrent active jobs,
  - proceeds to finishing flow (reuse existing finishing orchestration, skipping build).
- [x] 3.2 Return structured error with `reason: "missing_artifacts"` when build artifacts are absent.
- [x] 3.3 Return structured error with `reason: "job_already_active"` when rebuild guard rejects.
- [x] 3.4 Add regression tests for retry-from-finishing covering success path, missing artifacts error, and concurrent job rejection.

## 4. Cleanup Route

- [x] 4.1 Add `POST /api/homebrew/cleanup` route handler in `web/routes/toolkit_homebrew_routes.py` that:
  - validates job is in a terminal state (`completed`, `not_publishable`, `quarantined`, `failed`) OR `force=true`,
  - removes the upload workspace directory and all artifacts,
  - returns cleanup confirmation with removed path.
- [x] 4.2 Return error for non-terminal-state jobs without `force=true`.
- [x] 4.3 Add regression tests for cleanup covering terminal-state success, non-terminal rejection, and force-override behavior.

## 5. Frontend Artifact Visibility

- [x] 5.1 In `web/templates/module_toolkit.html`, add a read-only artifact checklist panel per job showing which artifacts exist and their sizes (no raw content).
- [x] 5.2 Enable retry-from-packet button only when `artifact_manifest.rebuild_eligible.from_packet` is `true`.
- [x] 5.3 Enable retry-from-finishing button only when `artifact_manifest.rebuild_eligible.from_finishing` is `true`.
- [x] 5.4 Show cleanup button for terminal-state jobs.
- [x] 5.5 No changes to gameplay runtime; toolkit UI only.

## 6. Verification

- [x] 6.1 Run targeted syntax checks: `python3 -m py_compile web/routes/toolkit_homebrew_routes.py`.
- [x] 6.2 Run unit tests for artifact manifest helper, retry routes, and cleanup route.
- [x] 6.3 Run existing homebrew route regressions to confirm no regressions.
- [x] 6.4 Run `openspec validate toolkit-homebrew-artifact-persistence`.
