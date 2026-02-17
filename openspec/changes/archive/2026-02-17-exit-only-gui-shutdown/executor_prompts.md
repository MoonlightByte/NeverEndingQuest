## Builder Execution Prompts - exit-only-gui-shutdown

Use this as a simple implementation guide tied to `tasks.md`.

---

## Execution Contract

MUST:
- MUST implement in task-group order (1 -> 5).
- MUST keep edits scoped to:
  - `web/web_interface.py`
  - `run_web.py`
  - `web/templates/game_interface.html`
- MUST preserve restart-on-0 behavior.
- MUST use intentional shutdown code `91` for GUI Exit path.
- MUST keep Python-visible output ASCII-only.

SHOULD:
- SHOULD add `# TABLETOP MODE:` markers on host-file hooks.
- SHOULD keep implementation additive and avoid unrelated refactors.

---

## Prompt 1 - Server Exit Handler

Implement tasks 1.x from `tasks.md`.

Scope:
- `web/web_interface.py`

Required:
- Upgrade `handle_user_exit()` from ack-only to ack + shutdown behavior.
- Emit `exit_acknowledged` before stop/exit path.
- Attempt graceful stop and enforce force-exit fallback with code `91`.

Verify:
- `python3 -m py_compile web/web_interface.py`

Report:
- List exact edited lines/functions and shutdown fallback behavior.

---

## Prompt 2 - Launcher Return-Code Branch

Implement tasks 2.x.

Scope:
- `run_web.py`

Required:
- Add explicit `elif result.returncode == 91` branch.
- Print shutdown message and break loop.
- Keep `returncode == 0` restart behavior unchanged.

Verify:
- `python3 -m py_compile run_web.py`

Report:
- Include final return-code branch logic summary.

---

## Prompt 3 - Exit Button Waiting State

Implement tasks 3.x.

Scope:
- `web/templates/game_interface.html`

Required:
- On Exit confirm, emit `user_exit` and show "Shutting Down..." wait UI.
- Disable `user-input` and `send-button` while waiting.
- Ensure `exit_acknowledged` listener exists and does not attempt restart.

Verify:
- Manual browser smoke notes for Exit click and visible waiting state.

Report:
- Provide concise behavior before/after comparison.

---

## Prompt 4 - Validation and Regression

Implement tasks 4.x.

Required checks:
- `python3 -m py_compile web/web_interface.py run_web.py`
- Manual smoke:
  1. Click Exit in GUI.
  2. Confirm server exits.
  3. Confirm launcher prints shutdown message and does not restart.
  4. Confirm reset/restore still restart normally.
  5. Confirm Ctrl+C still works.

Report:
- PASS/FAIL per check with short evidence lines.

---

## Prompt 5 - Final Handoff

Implement task 5.1.

Required:
- Ensure `tasks.md` remains aligned with implemented behavior.
- Provide final changed-file list and verification summary.

Ready signal:
- "Phase 1 Exit-only scaffolding is apply-ready."
