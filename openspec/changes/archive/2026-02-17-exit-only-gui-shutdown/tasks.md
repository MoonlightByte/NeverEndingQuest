## 1. Server Exit Handler (SocketIO)

- [x] 1.1 Update `handle_user_exit()` in `web/web_interface.py` to log exit intent and emit `exit_acknowledged` before shutdown.
- [x] 1.2 Implement graceful stop path (`socketio.stop()` where valid) and force-exit fallback with `os._exit(91)`.
- [x] 1.3 Mark host edits with `# TABLETOP MODE:` and keep behavior scoped only to `user_exit` flow.

## 2. Launcher Return-Code Contract

- [x] 2.1 Update `run_web.py` loop to handle return code `91` as intentional shutdown and break without restart.
- [x] 2.2 Preserve existing restart behavior for return code `0` and existing error behavior for unexpected codes.

## 3. GUI Exit UX State

- [x] 3.1 Update Exit button flow in `web/templates/game_interface.html` to emit `user_exit` and show deterministic "Shutting Down..." state.
- [x] 3.2 Disable `user-input` and `send-button` during shutdown wait state.
- [x] 3.3 Add/confirm `exit_acknowledged` listener behavior with no restart logic in browser.

## 4. Validation and Regression

- [x] 4.1 Run compile checks: `python3 -m py_compile web/web_interface.py run_web.py`.
- [x] 4.2 Manual smoke: click Exit -> acknowledgment path runs -> server exits -> launcher prints shutdown message and does not restart.
- [x] 4.3 Manual regression: reset/restore still trigger restart flow (return code `0`) and remain unchanged.
- [x] 4.4 Confirm terminal Ctrl+C still shuts down cleanly.

## 5. Builder Handoff

- [x] 5.1 Create `executor_prompts.md` with stepwise builder prompts and verification gates aligned to tasks 1.x-4.x.
