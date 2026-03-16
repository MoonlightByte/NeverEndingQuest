## 1. Shared prompt/context core

- [x] 1.1 Extract a shared DM-creation prompt/context builder rooted in startup behavior, with explicit `startup` and `mid_campaign` mode support, in a neutral utility layer.
- [x] 1.2 Route startup wizard DM creation to the shared prompt/context builder while preserving its existing interview loop and startup bootstrap semantics.
- [x] 1.3 Add focused regression coverage proving startup prompt assembly still works and mid-campaign prompt assembly gains the same canonical field/output contract.

## 2. Shared finalization and persistence core

- [x] 2.1 Extract a shared finalization service that handles candidate JSON extraction, sanitization, `audit_character_creation(...)`, corrective-note generation, and structured success/failure results.
- [x] 2.2 Standardize DM-created character persistence through one shared save helper instead of scattered direct writes.
- [x] 2.3 Add focused regression coverage for valid final JSON, invalid/incomplete final JSON, and fenced JSON across the shared finalizer.

## 3. Adapter rewiring

- [x] 3.1 Route `main.py:handle_character_creation_response()` through the shared finalization service while preserving creation-mode pause/resume behavior.
- [x] 3.2 Route startup wizard finalization through the same shared finalization/persistence contract while preserving iterative onboarding and `startup_incomplete` behavior.
- [x] 3.3 Route `/api/party/finalize_creation` through the shared finalizer or reduce it to a thin wrapper so duplicate finalization ownership is removed.
- [x] 3.4 Add focused regression coverage showing startup DM creation and mid-campaign `Create with DM` now share the same core contract without altering Roll Your Own or Add Existing.

## 4. Verification

- [x] 4.1 Run targeted Python compile checks for all touched backend files.
- [x] 4.2 Run targeted regression suites for prompt parity, finalization parity, and adapter-specific startup/mid-campaign behaviors.
- [x] 4.3 Capture a concise pass/fail verification summary in the builder report before proceeding to any follow-up cleanup.

### SHOULD Guidance

- SHOULD use micro-edits in large Python files (`utils/startup_wizard.py`, `main.py`) and run `python3 -m py_compile` after each touched file.
- SHOULD prefer thin wrappers over broad rewrites when moving startup and GUI call sites onto the shared core.
- SHOULD keep prompt assets ASCII-safe and avoid introducing new parallel prompt templates unless strictly necessary.
