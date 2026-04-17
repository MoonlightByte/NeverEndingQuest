## 1. Finisher Entry Orchestration

- [x] 1.1 Add upload job orchestration that allows only `ready_for_finishing` jobs to enter the shared finisher/publication path.
- [x] 1.2 Add explicit finisher/publication job states in `web/routes/toolkit_homebrew_routes.py` for `finishing`, `publishability_audit`, `completed`, `finishing_failed`, and `not_publishable`.
- [x] 1.3 Fail closed when finisher entry prerequisites are missing or inconsistent rather than silently skipping publication work.

## 2. Shared Finisher Attachment

- [x] 2.1 Reuse the shared toolkit finisher/publication stack rather than creating an upload-only publication path.
- [x] 2.2 Persist finisher and publication outputs into upload job/workspace artifacts, including final ready/publishable outcomes.
- [x] 2.3 Map shared finisher outcomes so only `publishable_status=pass` reaches `completed`, while publishability blockers land in `not_publishable`.

## 3. Operator Visibility And Reporting

- [x] 3.1 Update toolkit UI status/reporting so finisher/publication progress is distinct from build/readiness progress.
- [x] 3.2 Surface `ready_for_finishing`, `completed`, `finishing_failed`, and `not_publishable` with bounded operator-facing messages and artifact-backed detail.
- [x] 3.3 Preserve artifact/report parity expectations with the developer ingest path for representative successful and blocked modules.

## 4. Verification

- [x] 4.1 Add regression coverage for successful finisher completion, publishability-blocked completion, and finisher hard-failure behavior.
- [x] 4.2 Add parity-oriented tests or smoke assertions proving upload finishing uses the shared finisher/publication contract.
- [x] 4.3 Run targeted syntax checks, upload route regressions, finisher-adjacent tests, and `openspec validate toolkit-homebrew-finisher-publication-reattach`.
