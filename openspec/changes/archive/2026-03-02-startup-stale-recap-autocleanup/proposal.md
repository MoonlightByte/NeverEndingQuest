# Change Proposal: startup-stale-recap-autocleanup

## Why
- Gamers are hitting hard fail at `Failed to generate a valid response after 5 attempts`, and stale recap constraints can amplify retry failure loops.
- Startup cleanup exists but is not centralized and does not guarantee parity across all history channels.
- Manual cleanup should be optional developer tooling, not required tester workflow.

## Objective
- Enforce automatic stale recap cleanup at startup across both runtime history files.
- Preserve fail-closed desync prevention in the combat/action validation loop.
- Align script behavior with startup behavior using one canonical cleanup implementation.

## Non-goals
- Do not remove or weaken C1 fail-closed validation behavior in `main.py`.
- Do not redesign encounter/monster validation policy in this change.
- Do not change chat history schema or message shape.

## What Changes
- Add shared cleanup utility module for stale recap detection and removal.
- Run startup cleanup against:
  - `modules/conversation_history/conversation_history.json`
  - `modules/conversation_history/chat_history.json`
- Keep startup cleanup fail-open (missing or malformed files log degraded status; startup continues).
- Upgrade `scripts/cleanup_stale_recaps.py` with `--dry-run` and `--apply`, backed by shared utility.

## Capabilities
### New: startup-stale-recap-autocleanup
- Startup SHALL remove stale recap entries before recap injection.
- Cleanup SHALL be idempotent across repeated restarts.
- Startup logs SHALL report per-file removal counts and degraded conditions.

### New: stale-recap-cleanup-tooling-parity
- Script SHALL support `--dry-run` and `--apply` modes.
- Script SHALL use the same matcher/removal logic as startup runtime.
- Script SHALL emit deterministic summary output suitable for debugging.

## Impact
- Affected files:
  - `main.py`
  - `utils/session_cleanup.py` (new)
  - `scripts/cleanup_stale_recaps.py`
- Risk level: Low to Medium (startup-path additive changes only).
- Merge safety: Preserves upstream behavior; uses minimal `# TABLETOP MODE:` hooks.
