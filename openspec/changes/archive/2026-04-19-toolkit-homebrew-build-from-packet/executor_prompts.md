# Executor Prompts - toolkit-homebrew-build-from-packet

---

## Execution Contract

- MUST execute in order: task groups 1 -> 6.
- MUST keep upload approval separate from build execution.
- MUST keep host file edits minimal and mark required hooks with `# TABLETOP MODE:`.
- MUST preserve the existing concept-builder `start_build` workflow.
- MUST NOT attach post-build finishing, publication, or registry integration in this change.
- MUST keep Python-visible text ASCII only.

---

## Prompt 1 - Packet-To-Builder Facade

Implement tasks 1.1-1.3.

Scope:
- New upload-aware builder facade under `web/extensions/` or equivalent
- Shared contract helpers only if needed

Requirements:
- Read `normalized_packet.json` and `ui_review_snapshot.json` from the upload workspace.
- Validate the packet/review identity before build start.
- Persist `builder_input.json` with packet identity, build mode, and derived builder parameters.
- Reuse existing `builder_narrative.txt` when available rather than regenerating a second packet interpretation.

Verify before moving on:
- `python3 -m py_compile <new_facade_module> [shared helper files touched]`
- Focused transform smoke: approved packet workspace produces a non-empty `builder_input.json`.

---

## Prompt 2 - Approved Job Build Orchestration

Implement tasks 2.1-2.3.

Scope:
- `web/routes/toolkit_homebrew_routes.py`

Requirements:
- Add explicit build-start action for `approved_for_build` jobs.
- Allowed transition path MUST be `approved_for_build` -> `building` -> `build_completed|failed`.
- Preserve review approval as a separate decision path.
- Persist `build_result.json` on both success and failure.

Verify before moving on:
- `python3 -m py_compile web/routes/toolkit_homebrew_routes.py`
- Manual smoke or source-contract check: approval alone does not start the build.

---

## Prompt 3 - Builder Reuse Without Concept-Builder Regression

Implement tasks 3.1-3.3.

Scope:
- New shared helper extraction only if needed
- `web/web_interface.py` only if minimal helper extraction is required
- Existing builder integration surfaces used by the facade

Requirements:
- Use upstream `ModuleBuilder` as the default rich build engine.
- Keep the existing `start_build` concept-builder socket contract intact.
- Do not call the post-build finisher from the packet-driven upload path in this change.

Verify before moving on:
- `python3 -m py_compile web/web_interface.py [shared helper files touched]`
- Source-level check: concept-builder flow still targets its existing path.

---

## Prompt 4 - Toolkit UI And Reporting

Implement tasks 4.1-4.3.

Scope:
- `web/templates/module_toolkit.html`

Requirements:
- Show `approved_for_build`, `building`, and `build_completed` distinctly.
- Add a build-start control for approved upload jobs.
- Keep review buttons scoped to review states only.
- Display `build_result.json` details or equivalent job result payload after build completion/failure.

Verify before moving on:
- JS syntax check for inline template scripts.
- Manual smoke: approved job shows build-start control, not auto-build behavior.

---

## Prompt 5 - Regression Coverage

Implement tasks 5.1-5.3.

Scope:
- Upload route/job tests
- New packet-to-builder transform tests as needed

Requirements:
- Cover transform artifact persistence and provenance.
- Cover `approved_for_build` -> `building` -> `build_completed|failed` transitions.
- Include non-regression checks for concept-builder behavior and existing review flow.

Verify before moving on:
- Run all tests added in this phase.

---

## Prompt 6 - Final Verification

Implement task group 6.x.

Required final commands:
- `python3 -m py_compile [all modified Python files for this change]`
- Run phase-specific regression tests added in Prompt 5.
- Run inline JS syntax validation for `web/templates/module_toolkit.html` if touched.
- `openspec validate toolkit-homebrew-build-from-packet`

Manual smoke checklist:
1. Normalize and approve a Homebrew upload.
2. Confirm the approved job remains idle until explicit build start.
3. Start packet-driven build and confirm job enters `building`.
4. Confirm `builder_input.json` and `build_result.json` exist in the upload workspace.
5. Confirm successful build ends in `build_completed`, not final `completed`.

---

## Notes for Implementer

- Keep this slice narrow: build handoff and raw builder execution only.
- Do not attach semantic publication, finisher, or registry integration here.
- Prefer a small shared builder helper over broad refactoring if concept-builder reuse is needed.
