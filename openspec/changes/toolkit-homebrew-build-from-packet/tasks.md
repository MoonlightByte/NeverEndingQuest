## 1. Packet-To-Builder Facade

- [ ] 1.1 Add a dedicated upload-aware builder facade that reads `normalized_packet.json` and `ui_review_snapshot.json` from an approved upload workspace.
- [ ] 1.2 Persist `builder_input.json` as the canonical packet-to-builder transform artifact before build execution starts.
- [ ] 1.3 Derive builder invocation parameters from the normalized packet and existing builder narrative while preserving packet provenance.

## 2. Upload Job Build Orchestration

- [ ] 2.1 Update `web/routes/toolkit_homebrew_routes.py` to add an explicit build-start action for `approved_for_build` jobs.
- [ ] 2.2 Transition approved jobs through `building` and into a distinct post-build state such as `build_completed` on success, or `failed` on build error.
- [ ] 2.3 Preserve current review-gate semantics so approval does not auto-start the build.

## 3. Builder Reuse And Scope Control

- [ ] 3.1 Reuse the upstream `ModuleBuilder` path as the default rich-generation engine for packet-driven builds.
- [ ] 3.2 Keep the concept-builder socket flow intact and avoid breaking existing `start_build` behavior.
- [ ] 3.3 Ensure this change stops before post-build finishing, semantic publication probes, or registry integration.

## 4. Toolkit Reporting Surface

- [ ] 4.1 Update `web/templates/module_toolkit.html` to show `approved_for_build`, `building`, and `build_completed` distinctly.
- [ ] 4.2 Add or expose a build-start control for approved upload jobs without conflating it with the review approval action.
- [ ] 4.3 Surface persisted `build_result.json` details in the toolkit status area when packet-driven builds succeed or fail.

## 5. Regression Coverage

- [ ] 5.1 Add or extend tests for packet-to-builder transform shape and provenance persistence.
- [ ] 5.2 Extend upload job tests for `approved_for_build` -> `building` -> `build_completed|failed` transitions.
- [ ] 5.3 Add non-regression checks that the concept-builder flow and existing review behavior still work unchanged.

## 6. Verification

- [ ] 6.1 Run targeted syntax validation for modified Python files and any JS-bearing template logic touched by build-state reporting.
- [ ] 6.2 Run targeted regression tests for packet transformation, upload job build transitions, and concept-builder non-regression.
- [ ] 6.3 Run `openspec validate toolkit-homebrew-build-from-packet`.
