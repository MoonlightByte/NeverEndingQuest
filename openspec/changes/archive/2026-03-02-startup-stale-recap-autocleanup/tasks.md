# Tasks: startup-stale-recap-autocleanup

## 1. Shared Cleanup Utility
- [x] 1.1 Create `utils/session_cleanup.py` with canonical stale recap matcher (`SESSION RESUME RECAP ONLY`) and removal helpers.
- [x] 1.2 Add file-level cleanup helper that supports report-only and apply modes.
- [x] 1.3 Add structured return payload for counts/status to support logs and scripts.

## 2. Startup Integration
- [x] 2.1 Update `main.py` startup path to call shared cleanup for `conversation_history.json` and `chat_history.json`.
- [x] 2.2 Ensure cleanup runs before recap injection logic.
- [x] 2.3 Keep startup fail-open on cleanup errors; add clear TABLETOP MODE log lines.

## 3. Script Parity
- [x] 3.1 Refactor `scripts/cleanup_stale_recaps.py` to use `utils/session_cleanup.py`.
- [x] 3.2 Add CLI modes: `--dry-run` and `--apply` (safe default dry-run when mode omitted).
- [x] 3.3 Emit deterministic summary output (per-file removed/remaining/errors).

## 4. Regression Coverage
- [x] 4.1 Add targeted tests for matcher/removal idempotency and malformed/missing file fail-open behavior.
- [x] 4.2 Add script behavior tests for `--dry-run` and `--apply` mode contracts.

## 5. Verification
- [x] 5.1 Run compile checks:
  - `python3 -m py_compile main.py utils/session_cleanup.py scripts/cleanup_stale_recaps.py`
- [x] 5.2 Run targeted tests for session cleanup and script mode behavior.
- [x] 5.3 Run OpenSpec validation:
  - `openspec validate startup-stale-recap-autocleanup`
- [x] 5.4 Document verification results in change notes or implementation notes.
