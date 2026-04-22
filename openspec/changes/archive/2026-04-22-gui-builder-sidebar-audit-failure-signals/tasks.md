# Tasks: gui-builder-sidebar-audit-failure-signals

## 1. Contract and Payload Shaping

- [X] 1.1 Add a small persisted-report reader/helper in `core/generators/module_stitcher.py` that fail-opens on missing or malformed `toolkit_build_report.json`.
- [X] 1.2 Derive additive compact fields for each module entry, including `brief_failure` and `media_generator_needed`.
- [X] 1.3 Keep the existing module-list payload contract intact and append new fields only when derivation succeeds.
- [X] 1.4 Verify no live audit script execution is introduced into the sidebar request path.

## 2. Failure and Handoff Mapping

- [X] 2.1 Implement a bounded mapping from persisted report content to brief user-facing failure strings.
- [X] 2.2 Implement detection for manual `Module Media Generator` handoff from persisted report categories or media-policy fields.
- [X] 2.3 Verify the mapping produces useful brief output for `Murder_at_the_Drowning_Lass` and `The_Ancients_Lab` using current local artifacts.

## 3. Sidebar Rendering

- [X] 3.1 Update `web/templates/module_toolkit.html` to render the brief red failure line below `Plot Points` when present.
- [X] 3.2 Update `web/templates/module_toolkit.html` to render a visually secondary manual media-generator line when `media_generator_needed` is true.
- [X] 3.3 Mirror the same rendering behavior in `web/templates/module_builder.html` so duplicate renderers remain aligned.
- [X] 3.4 Preserve existing module card selection behavior and layout stability.

## 4. Verification

- [X] 4.1 Add targeted regression coverage for persisted-report parsing and fail-open behavior.
- [X] 4.2 Add targeted regression coverage for brief-failure/media-handoff rendering contracts.
- [X] 4.3 Run syntax and relevant targeted test commands for modified files.
- [X] 4.4 Manually verify that failed modules show concise guidance while modules without report data continue rendering normally.

## Guidance

- SHOULD keep the failure text to one short line where possible.
- SHOULD avoid introducing new shared caching unless request-time parsing proves too noisy.
- SHOULD prefer helper extraction over expanding socket handlers or templates with report-parsing logic.
