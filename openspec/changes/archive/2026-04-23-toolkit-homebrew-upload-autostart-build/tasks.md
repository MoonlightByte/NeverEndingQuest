## 1. Backend flow update

- [x] 1.1 Replace the post-normalization `awaiting_review` happy-path stop with direct build progression.
- [x] 1.2 Ensure auto-start reuses the existing packet build path instead of duplicating build orchestration.
- [x] 1.3 Preserve collision detection and `awaiting_overwrite_confirmation` behavior for existing module slugs.
- [x] 1.4 Preserve normalized packet artifacts and reporting metadata needed by status/retry flows.

## 2. Toolkit UI update

- [x] 2.1 Remove the visible review/approve/reject/start controls from the Homebrew upload flow.
- [x] 2.2 Keep structured job progress, terminal status, and overwrite confirmation UX intact.
- [x] 2.3 Ensure the UI transitions cleanly from import into active build or confirmation-needed states.

## 3. Contract and regression coverage

- [x] 3.1 Update route/spec tests that currently require `awaiting_review` and manual approval before build.
- [x] 3.2 Add/adjust coverage for direct auto-start after normalization.
- [x] 3.3 Preserve explicit coverage for overwrite confirmation, backup metadata, retry-from-packet, and artifact visibility.
- [x] 3.4 Run targeted verification for the changed OpenSpec change and affected tests.
