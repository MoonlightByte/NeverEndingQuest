# Executor Prompts: startup-stale-recap-autocleanup

## Execution Contract
- **MUST** preserve existing fail-closed validation guard (`Failed to generate a valid response after 5 attempts`) and desync prevention semantics.
- **MUST** centralize stale recap detection/removal in one shared utility (`utils/session_cleanup.py`).
- **MUST** run startup cleanup for both history files before recap injection.
- **MUST** keep startup cleanup fail-open (log + continue) on missing/malformed files.
- **MUST** keep edits merge-safe and additive with `# TABLETOP MODE:` markers in host files.
- **SHOULD** use small anchored edits, one bounded patch per file section.
- **SHOULD** run `py_compile` immediately after each touched Python file.

## Prompt 1 - Shared Utility Foundation
**Step ID:** 1
**Tier:** MUST

Create `utils/session_cleanup.py` with canonical helpers for stale recap handling.

### Required scope
- Add marker constant for `SESSION RESUME RECAP ONLY`.
- Add pure matcher/removal helpers for message arrays.
- Add file cleanup helper supporting report-only vs apply mode.
- Return structured summary (`status`, `removed_count`, `total_before`, `total_after`, `error`).

### Verification gate
- `python3 -m py_compile utils/session_cleanup.py`

### Next step
Proceed to Prompt 2 only after compile passes.

---

## Prompt 2 - Startup Integration in main.py
**Step ID:** 2
**Tier:** MUST

Wire shared cleanup into startup flow before recap injection.

### Required scope
- In startup initialization path, run cleanup for:
  - `modules/conversation_history/conversation_history.json`
  - `modules/conversation_history/chat_history.json`
- Keep startup fail-open: if cleanup errors, log degraded status and continue startup.
- Preserve existing recap injection behavior and fail-closed runtime validation logic.

### Verification gate
- `python3 -m py_compile main.py`

### Next step
Proceed to Prompt 3 only after compile passes.

---

## Prompt 3 - Script Parity and CLI Modes
**Step ID:** 3
**Tier:** MUST

Refactor `scripts/cleanup_stale_recaps.py` to use shared cleanup utility and deterministic CLI modes.

### Required scope
- Add `--dry-run` and `--apply` flags.
- Default to safe report-only behavior when mode omitted.
- Use the same matcher/removal logic from `utils/session_cleanup.py` (no duplicate logic).
- Emit deterministic summary output with per-file counts.

### Verification gate
- `python3 -m py_compile scripts/cleanup_stale_recaps.py`
- `python3 scripts/cleanup_stale_recaps.py --dry-run`

### Next step
Proceed to Prompt 4 only after script executes cleanly.

---

## Prompt 4 - Regression Coverage
**Step ID:** 4
**Tier:** SHOULD

Add targeted tests for cleanup correctness and idempotency.

### Suggested scope
- Matcher/removal unit tests (exact marker match, idempotency).
- File cleanup tests (missing file, malformed JSON, apply vs dry-run behavior).
- Script mode tests (`--dry-run`, `--apply`).

### Verification gate
- Run targeted tests you add.
- Keep failures actionable and deterministic.

### Next step
Proceed to Prompt 5.

---

## Prompt 5 - Final Verification and OpenSpec Validation
**Step ID:** 5
**Tier:** MUST

Run end-to-end verification for this change.

### Required checks
- `python3 -m py_compile main.py utils/session_cleanup.py scripts/cleanup_stale_recaps.py`
- Run targeted cleanup tests
- `openspec validate startup-stale-recap-autocleanup`

### Completion criteria
- Compile checks pass
- Startup cleanup covers both files
- Script parity confirmed
- OpenSpec validation returns valid
