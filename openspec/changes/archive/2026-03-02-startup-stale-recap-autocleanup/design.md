# Design: startup-stale-recap-autocleanup

## Context
`main.py` currently performs stale recap cleanup inline for `conversation_history.json` before startup recap injection. In practice, stale recap entries can also exist in `chat_history.json`, and standalone cleanup script behavior is not guaranteed to stay in sync with runtime cleanup logic.

This change creates a single canonical cleanup path and applies it automatically at startup so players are not blocked by maintenance chores.

## Goals
- Ensure startup cleanup covers both conversation and chat history stores.
- Centralize stale recap matching/removal in one utility shared by runtime and script.
- Keep startup resilient (fail-open on file issues) while preserving fail-closed gameplay validation semantics.

## Non-Goals
- No redesign of validation retry loop behavior in this change.
- No changes to encounter builder policy or monster creation gates.
- No schema changes for conversation/chat history payloads.

## Decisions

### Decision 1: Centralize recap cleanup in a shared utility module
- **Decision:** Add `utils/session_cleanup.py` as canonical source for stale recap detection/removal.
- **Rationale:** Prevent drift between startup and script behavior.
- **Alternative considered:** Keep inline cleanup in `main.py` and duplicate logic in script. Rejected due to drift risk.

**Proposed API (MUST-level contract):**
- `is_stale_resume_recap_message(message: Dict[str, Any]) -> bool`
- `remove_stale_resume_recaps(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]`
- `cleanup_history_file(path: str, apply_changes: bool) -> Dict[str, Any]`

### Decision 2: Apply cleanup before startup recap injection
- **Decision:** Invoke cleanup for both history files immediately after load and before `check_and_inject_return_message()` recap injection logic.
- **Rationale:** Prevent old recap constraints from remaining in context when startup recap is injected.
- **Alternative considered:** Cleanup only after injection. Rejected because stale constraints can still contaminate model context.

### Decision 3: Keep startup cleanup fail-open, keep gameplay validation fail-closed
- **Decision:** On missing/malformed history files, startup logs degraded status and continues.
- **Rationale:** Cleanup failure should not block server startup.
- **Invariant:** The existing 5-attempt fail-closed gameplay guard remains unchanged.

### Decision 4: Script parity with deterministic CLI modes
- **Decision:** `scripts/cleanup_stale_recaps.py` supports `--dry-run` and `--apply`, calling shared utility.
- **Rationale:** Provide developer support and reproducibility without requiring manual JSON edits.
- **Behavior:**
  - `--dry-run`: report only; no writes.
  - `--apply`: persist removals.
  - no mode: default to `--dry-run` (safe default).

## Risks and Mitigations
- **Risk:** False positive deletion.
  - **Mitigation:** Match only explicit marker text `SESSION RESUME RECAP ONLY` in message content.
- **Risk:** Runtime startup regression.
  - **Mitigation:** Keep cleanup additive, bounded to known files, and fail-open.
- **Risk:** Script/runtime drift returns in future.
  - **Mitigation:** Script imports shared utility instead of reimplementing logic.

## Migration Plan
1. Add shared utility and unit-test matcher/removal behavior.
2. Replace inline startup cleanup with shared utility calls for both files.
3. Update script to shared utility + CLI modes.
4. Run compile/tests and OpenSpec validation.

## Rollback Plan
- Revert `main.py` startup integration and utility import.
- Keep script fallback behavior (or revert script changes).
- No data migration required; cleanup is idempotent and non-schema.

## Verification Strategy
- `python3 -m py_compile main.py utils/session_cleanup.py scripts/cleanup_stale_recaps.py`
- `python3 scripts/cleanup_stale_recaps.py --dry-run`
- `python3 scripts/cleanup_stale_recaps.py --apply` (on test fixture or local sample)
- `openspec validate startup-stale-recap-autocleanup`
