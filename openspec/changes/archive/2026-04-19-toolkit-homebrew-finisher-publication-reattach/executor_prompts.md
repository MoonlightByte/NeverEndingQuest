## Builder Prompt

Implement `toolkit-homebrew-finisher-publication-reattach` from `plans/module-uploader.md` Phase 6.

Guardrails:

1. Treat `ready_for_finishing` as the only valid successful entry state for this slice.
2. Reuse the shared finisher/publication stack; do not create an upload-only publication implementation.
3. Preserve the distinction between `build_completed`, `ready_for_finishing`, `completed`, and `not_publishable`.
4. Allow registry/world integration only when the shared finisher reports `publishable_status=pass`.
5. Preserve fail-closed behavior for missing prerequisites, finisher defects, and publishability blockers.
6. Keep concept-builder flow unchanged.
7. Keep normalization, packet build, and structural readiness logic out of scope unless a thin adapter is strictly required.

Suggested implementation order:

1. Extend upload job states and route orchestration for finisher entry.
2. Add a thin adapter from upload jobs to the shared finisher/publication stack.
3. Persist finisher/publication artifacts and map outcomes into upload job states.
4. Update toolkit UI/progress reporting for finisher/publication visibility.
5. Add regression/parity coverage and validate the change.

Verification expectations:

1. A `ready_for_finishing` upload can reach `completed` only when publishability passes.
2. A structurally ready but publishability-blocked upload lands in `not_publishable` with preserved artifacts.
3. A finisher/runtime defect lands in `finishing_failed`, not silent success.
4. Upload finishing/reporting remains aligned with the shared developer finisher path.
