## Why

The current GUI Exit button only acknowledges intent and attempts to close the browser tab. It does not stop the Python server process, so operators still need terminal Ctrl+C. For tabletop sessions, the easiest immediate improvement is an Exit-only flow that cleanly stops the running server from the existing GUI button.

## What Changes

- Implement Phase 1 only: Exit from GUI triggers intentional server shutdown.
- Update `@socketio.on('user_exit')` handler in `web/web_interface.py` to:
  - log the user exit event,
  - emit `exit_acknowledged`,
  - stop the SocketIO server and exit process with dedicated code `91`.
- Update `run_web.py` launcher loop to treat return code `91` as intentional shutdown:
  - print terminal shutdown message,
  - break loop (no automatic restart).
- Update `web/templates/game_interface.html` Exit button flow to:
  - emit `user_exit`,
  - show deterministic "Shutting Down..." UI state,
  - disable input while server exits.
- Preserve existing restart behavior for return code `0` (reset/restore paths).

MUST constraints:
- MUST keep full implementation in existing Exit button flow (no new control API).
- MUST preserve restart-on-0 behavior for reset/restore.
- MUST use intentional non-zero exit code (`91`) to distinguish user shutdown from restart.
- MUST fail closed on exit path (if graceful stop fails, force process exit).

SHOULD guidance:
- SHOULD keep host edits minimal and mark host hooks with `# TABLETOP MODE:` comments.
- SHOULD keep UI changes additive without redesigning Settings or layout.

### Non-goals

- No Enter/restart button in GUI for this phase.
- No persistent supervisor/watcher process.
- No localhost control API (`/control/start`, `/control/stop`) in this phase.
- No changes to combat, narration, or save semantics.

## Capabilities

### New Capabilities
- `gui-exit-only-graceful-shutdown`: GUI Exit triggers intentional server shutdown with launcher-aware return-code handling.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `web/web_interface.py`
  - `run_web.py`
  - `web/templates/game_interface.html`
- APIs/system surfaces:
  - Existing SocketIO event `user_exit` gains shutdown side effects.
  - Existing return code contract in launcher expands with dedicated intentional shutdown code `91`.
- Dependencies:
  - No new dependencies.
- Rollout risk:
  - Low to medium (process lifecycle changes).
  - Mitigated by explicit return-code branching and fallback force-exit behavior.
- Fallback strategy:
  - If graceful stop path fails, force process exit with code `91`.
  - If user does not use GUI Exit, terminal Ctrl+C remains valid.
- Merge-safety/SP-MP impact:
  - Additive and merge-safe; behavior applies consistently in single-player and tabletop modes.
