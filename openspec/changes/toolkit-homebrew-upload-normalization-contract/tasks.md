## 1. Contract Foundations

- [x] 1.1 Add the canonical normalized packet contract for toolkit Homebrew uploads, including provenance and rights-classification fields required by `plans/module-uploader.md`.
- [x] 1.2 Add a dedicated toolkit upload artifact workspace helper for `user_uploads/toolkit/homebrew_md/<job_id>/` with canonical filenames for source, preflight, packet, and later build/report artifacts.
- [x] 1.3 Ensure the contract/workspace layer stays separate from the source-anonymous world-narrative ingestion lane and document that boundary in code comments or helper docstrings where needed.

## 2. Preflight Routing Rework

- [x] 2.1 Update `scripts/homebrew_preflight.py` so readable ambiguous markdown routes to a normalization-required outcome instead of a generic terminal structure failure.
- [x] 2.2 Preserve deterministic-ready behavior for room-based and ACT/LOCATION sources and preserve fail-closed behavior for unreadable or invalid uploads.
- [x] 2.3 Extend structured preflight output to expose routing-oriented fields needed by the toolkit upload job layer.

## 3. Upload Job Contract Updates

- [x] 3.1 Update toolkit upload job handling in `web/routes/toolkit_homebrew_routes.py` to create artifact workspaces and persist source/preflight/packet artifacts for readable uploads.
- [x] 3.2 Update `scripts/homebrew_ingest_dev.py` contract handling so normalization-required routing can stop cleanly with preserved artifacts instead of collapsing to a misleading hard failure.
- [x] 3.3 Update toolkit result/reporting surfaces so upload jobs can show authoritative routing states before strict ingest begins while preserving the existing concept-builder flow.

## 4. Regression Coverage

- [x] 4.1 Add or extend tests for preflight routing classes, including readable normalization-required markdown, deterministic-ready markdown, and unreadable-invalid sources.
- [x] 4.2 Add or extend tests for toolkit upload job workspace creation, packet placeholder persistence, and routing-state reporting.
- [x] 4.3 Add or extend tests that confirm unsupported file types still fail early and concept-builder behavior remains unaffected.

## 5. Verification

- [x] 5.1 Run targeted syntax/compile validation for modified Python files.
- [x] 5.2 Run targeted test coverage for preflight and toolkit upload/job contract changes.
- [x] 5.3 Run `openspec validate toolkit-homebrew-upload-normalization-contract`.
