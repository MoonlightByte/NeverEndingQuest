# Tasks: GUI Builder Semantic Remediation Reporting

## 1. Reporting Contract

- [x] 1.1 Define the exact toolkit reporting contract for semantic-only versus mixed media-plus-semantic blocker cases.
- [x] 1.2 Identify the compatibility-safe payload fields the toolkit UI SHALL read for semantic remediation detail.

## 2. Toolkit Rendering

- [x] 2.1 Implement a semantic remediation formatter/path for toolkit build and upload result surfaces.
- [x] 2.2 Render structured semantic blocker detail from `blocking_findings` when present, with safe fallback to `blocking_errors`.
- [x] 2.3 Preserve explicit media handoff for pure media-only debt and explicit mixed-failure messaging when both classes are present.

## 3. Regression Coverage

- [x] 3.1 Add or update targeted tests proving semantic-only publishability blockers render a semantic remediation lane.
- [x] 3.2 Add or update targeted tests proving mixed media plus semantic blockers remain failed and render both debt classes distinctly.
- [x] 3.3 Add or update targeted tests proving raw JSON dump behavior is no longer the only operator-facing output for semantic blocker cases.

## 4. Verification

- [x] 4.1 Run `python3 -m py_compile web/web_interface.py`.
- [x] 4.2 Run targeted toolkit/reporting tests for the new semantic remediation path.
- [x] 4.3 Verify against representative module payloads covering semantic-only and mixed-failure outcomes.

## SHOULD Guidance

- SHOULD keep the first implementation narrow to toolkit surfaces already used by builder/upload flows.
- SHOULD prefer additive rendering helpers over status-contract rewrites.
- SHOULD preserve raw payload visibility behind the formatted remediation summary for debugging.
