# Tasks: GUI Builder Media Handoff Semantics

## 1. Finisher Outcome Contract

- [X] 1.1 Define the exact toolkit finisher contract for media-only debt versus true build failure.
- [X] 1.2 Identify the compatibility-safe payload/report fields needed for explicit handoff semantics.

## 2. Finisher Implementation

- [X] 2.1 Implement bounded success-with-handoff semantics in `web/extensions/toolkit_module_finisher.py`.
- [X] 2.2 Preserve explicit missing media debt details in the returned payload/report.
- [X] 2.3 Route the operator to `Module Builder -> Module Media Generator` as the manual next step.

## 3. Regression Coverage

- [X] 3.1 Add or update targeted tests proving media-only debt yields successful build handoff semantics.
- [X] 3.2 Add or update targeted tests proving real structural failures still fail.

## 4. Verification

- [X] 4.1 Run `python3 -m py_compile web/extensions/toolkit_module_finisher.py`.
- [X] 4.2 Run targeted finisher/build-result tests.
- [X] 4.3 Verify against a real toolkit media-debt module and capture the resulting handoff payload/report.
