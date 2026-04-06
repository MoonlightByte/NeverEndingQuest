## 1. Toolkit Upload Entry Surface

- [X] 1.1 Add a toolkit UI section for Homebrew markdown upload in `web/templates/module_toolkit.html` that clearly scopes the feature to `.md` only.
- [X] 1.2 Add backend upload/job handling that accepts markdown sources and prevents concurrent ingest jobs from colliding.
- [X] 1.3 Ensure toolkit upload handling does not depend on `modules/ingest/` watcher semantics or archive polling.

## 2. Shared Ingest Pipeline Reuse

- [X] 2.1 Route toolkit markdown imports through `scripts/homebrew_ingest_dev.py::run_ingest_pipeline(...)` without duplicating stage orchestration.
- [X] 2.2 Preserve pipeline `status`, `stage`, `exit_code`, and nested result payloads as the authoritative ingest outcome contract.
- [X] 2.3 Add defensive handling for invalid file type, unreadable upload, pipeline exception, and duplicate in-flight request paths.

## 3. Toolkit Result Reporting

- [X] 3.1 Add toolkit-visible progress and result states for success, degraded success, failed, and quarantined outcomes.
- [X] 3.2 Surface quarantine reasons and preflight/validation guidance in the toolkit UI without requiring filesystem-sidecar inspection.
- [X] 3.3 Preserve the existing concept Module Builder flow and verify it remains usable while the new upload flow is present.

## 4. Verification

- [X] 4.1 Add regression coverage for upload validation, direct pipeline invocation, duplicate job guarding, and structured result mapping.
- [X] 4.2 Run targeted compile/syntax validation for modified Python and toolkit frontend files.
- [ ] 4.3 Smoke-test toolkit `.md` import with at least one valid markdown source and one expected quarantine case.
