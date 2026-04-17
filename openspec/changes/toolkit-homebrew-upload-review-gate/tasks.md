## 1. Review Contract Helpers

- [x] 1.1 Extend `utils/toolkit_homebrew_upload_contract.py` with helper functions for loading normalized packet artifacts and persisting `ui_review_snapshot.json` with auditable decision metadata.
- [x] 1.2 Define fail-closed validation rules for review decisions so approval or rejection cannot succeed when packet artifacts are missing, invalid, or snapshot persistence fails.

## 2. Job State and Route Handling

- [x] 2.1 Update `web/routes/toolkit_homebrew_routes.py` to expose a review-detail read path for normalized upload jobs using the artifact workspace as the truth source.
- [x] 2.2 Add approve and reject route handlers in `web/routes/toolkit_homebrew_routes.py` that validate current job state under the job lock, persist review snapshots, and transition jobs to `approved_for_build` or `rejected`.
- [x] 2.3 Prevent unreviewed jobs from being treated as build-ready and preserve authoritative `stage`, `pipeline_status`, and `routing_outcome` fields across review transitions.

## 3. Toolkit Review UI

- [x] 3.1 Update `web/templates/module_toolkit.html` to render a review panel for `awaiting_review` Homebrew upload jobs with curated packet fields, warnings, and assumptions.
- [x] 3.2 Add client-side approve and reject actions that call the new review routes, refresh job state cleanly, and distinguish review approval from final build completion.
- [x] 3.3 Keep the existing concept-builder workflow and existing non-review upload reporting behavior unchanged.

## 4. Regression Coverage

- [x] 4.1 Extend `scripts/test_toolkit_homebrew_md_upload_routes.py` for review-detail loading, approve/reject transitions, snapshot persistence, and fail-closed missing-packet behavior.
- [x] 4.2 Add or extend UI-facing contract coverage for review-state rendering and no-regression concept-builder behavior.

## 5. Verification

- [x] 5.1 Run targeted syntax validation for modified Python files and any extracted JS-bearing template logic affected by the review UI change.
- [x] 5.2 Run targeted regression tests for toolkit Homebrew upload review routes and UI/reporting contract changes.
- [x] 5.3 Run `openspec validate toolkit-homebrew-upload-review-gate`.
