# Tasks: GUI Builder Mixed Failure Classification

## 1. Mixed-Failure Contract
- [x] 1.1 Define the exact boundary between pure media-only debt and mixed failure.
- [x] 1.2 Identify the publishability fields finisher consumers must read to preserve that boundary.

## 2. Classification Implementation
- [x] 2.1 Tighten finisher classification so success-with-media-handoff requires a pure media-only profile.
- [x] 2.2 Preserve explicit failed semantics for mixed media plus semantic/content blockers.
- [x] 2.3 Preserve media debt visibility in failed mixed-case payloads.

## 3. Regression Coverage
- [x] 3.1 Add targeted tests for pure media-only success-with-handoff.
- [x] 3.2 Add targeted tests for mixed media plus semantic blocker failure.
- [x] 3.3 Add targeted tests for semantic-only failure.

## 4. Verification
- [x] 4.1 Run `python3 -m py_compile web/extensions/toolkit_module_finisher.py scripts/audit_module_publishability.py`.
- [x] 4.2 Run targeted finisher/publishability tests.
- [x] 4.3 Capture one mixed real-module payload example proving the outcome remains failed.
