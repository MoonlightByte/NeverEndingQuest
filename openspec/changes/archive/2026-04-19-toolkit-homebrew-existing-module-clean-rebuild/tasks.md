## 1. Collision Detection And Confirmation

- [x] 1.1 Add reviewed-packet module-slug collision detection before packet-driven Homebrew build begins in `web/routes/toolkit_homebrew_routes.py`.
- [x] 1.2 Add toolkit UI state and modal wiring in `web/templates/module_toolkit.html` so existing-module collisions require explicit operator confirmation before destructive rebuild proceeds.
- [x] 1.3 Persist rebuild intent and collision metadata in Homebrew job/workspace artifacts without changing the legacy concept-builder workflow.

## 2. Backup And Clean Rebuild Orchestration

- [x] 2.1 Add a shared helper under `web/extensions/` to create a timestamped backup of `modules/<slug>` and fail closed if backup creation fails.
- [x] 2.2 Add a clean-target helper that removes the active module directory only after backup success and before packet build starts.
- [x] 2.3 Resume the existing packet build and structural readiness pipeline after successful backup and cleanup so repeated uploads use the same post-clean build path as fresh uploads.

## 3. Reporting And Operator Visibility

- [x] 3.1 Extend toolkit Homebrew job reporting to expose rebuild mode, backup path/outcome, and rebuild-preparation states distinctly from ordinary build progress.
- [x] 3.2 Update toolkit result/status text so cancel, backup failure, cleanup failure, and confirmed rebuild outcomes are operator-visible and bounded.

## 4. Verification

- [x] 4.1 Add route and UI-adjacent regression coverage for collision detection, cancel path, confirmed rebuild path, and backup-failure fail-closed behavior.
- [x] 4.2 Add focused helper tests for backup creation and clean-rebuild sequencing against a temporary module directory.
- [x] 4.3 Run targeted syntax checks, Homebrew route/regression tests, and `openspec validate toolkit-homebrew-existing-module-clean-rebuild`.
