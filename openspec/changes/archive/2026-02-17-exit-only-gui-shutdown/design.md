## Context

`plans/exit-enter.md` defines a two-phase approach. Phase 1 is intentionally small: Exit-only from GUI, no watcher, no restart-from-browser. Current runtime already has an Exit button and `user_exit` socket event, but it only logs and acknowledges intent. The launcher currently restarts on return code `0` and treats other codes as error.

This design converts the existing Exit intent into deterministic process shutdown using a dedicated return code contract between server and launcher.

## Goals / Non-Goals

**Goals:**
- Make GUI Exit equivalent to intentional process shutdown (operator no longer needs Ctrl+C).
- Keep implementation minimal and aligned with existing plan Phase 1.
- Preserve reset/restore restart semantics.
- Provide clear user-facing and terminal-facing shutdown messaging.

**Non-Goals:**
- Add Enter/restart capability from browser.
- Introduce a supervisor control API.
- Change browser auto-open behavior or add multi-process orchestration.

## Decisions

### 1) Dedicated exit code contract (`91`) between web process and launcher
Decision: `web/web_interface.py` exits with code `91` for intentional GUI shutdown. `run_web.py` handles `91` as normal intentional stop and does not restart.

Rationale:
- Distinguishes intentional stop from restart path (`0`) and unexpected failures.
- Keeps launcher logic simple and explicit.

Alternatives considered:
- Reuse exit code `0`: rejected because `run_web.py` currently maps `0` to restart.

### 2) Exit trigger remains the existing `user_exit` socket event
Decision: keep existing event and upgrade its behavior to perform graceful shutdown.

Rationale:
- Minimal surface change.
- No new endpoint or control channel required.

Alternatives considered:
- New REST endpoint for shutdown: rejected for Phase 1 simplicity and added security surface.

### 3) Best-effort graceful stop with force-exit fallback
Decision: handler emits `exit_acknowledged`, attempts server stop, and force-exits with code `91` on failure.

Rationale:
- Avoids hanging process on partial shutdown failures.
- Meets operator expectation that Exit always exits.

Alternatives considered:
- Graceful-only stop without fallback: rejected due to reliability risk.

### 4) UI enters deterministic shutdown state after Exit confirmation
Decision: on Exit confirm, client emits `user_exit`, shows shutdown overlay/message, and disables input controls.

Rationale:
- Prevents further actions during shutdown window.
- Gives user immediate feedback when browser cannot self-close.

Alternatives considered:
- Attempt immediate tab close only: rejected because most browsers block programmatic close.

### 5) Preserve restart-on-0 semantics for existing flows
Decision: keep `run_web.py` behavior unchanged for return code `0` so reset/restore still restart automatically.

Rationale:
- Avoids regressions in existing restart-dependent workflows.

## MUST / SHOULD Contract

MUST:
- MUST use `91` as intentional GUI shutdown code.
- MUST preserve restart-on-0 behavior.
- MUST keep Exit flow fail-closed (force exit on shutdown errors).
- MUST avoid introducing watcher/control API in this change.

SHOULD:
- SHOULD mark host file hooks with `# TABLETOP MODE:`.
- SHOULD keep JS/CSS changes additive and scoped to Exit flow only.
- SHOULD keep terminal output concise and operator-readable.

## Risks / Trade-offs

- [Process exits before client sees acknowledgment] -> Mitigation: emit `exit_acknowledged` before stop/exit and show local shutdown UI immediately.
- [Environment-specific `socketio.stop()` behavior] -> Mitigation: force-exit fallback path with code `91`.
- [Regression in reset/restore restart behavior] -> Mitigation: explicit launcher branching and manual smoke for return code `0` paths.

## Migration Plan

1. Update `web/web_interface.py` `handle_user_exit()` to perform acknowledgment + shutdown + code `91` exit.
2. Update `run_web.py` return-code handling to treat `91` as intentional stop and break.
3. Update Exit button behavior in `web/templates/game_interface.html` to show shutdown state and disable inputs.
4. Verify compile and behavior:
   - `python3 -m py_compile web/web_interface.py run_web.py`
   - Manual smoke: GUI Exit -> process stops -> launcher prints shutdown message.
   - Manual regression: reset/restore path still restarts with return code `0` semantics.

Rollback strategy:
- Revert `handle_user_exit()` to ack-only behavior.
- Remove `91` branch from `run_web.py` and keep previous return-code handling.
- Revert Exit UI overlay changes.

## Open Questions

- Should final shutdown log text be standardized as `[Py] ...` in both `print` and logger output, or keep existing `INFO:` prefix style?
- Should Exit be restricted to active facilitator session only if multiple clients are connected?
