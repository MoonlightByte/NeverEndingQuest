## 1. Start-Game Preflight Helper

- [x] 1.1 Add `web/extensions/start_game_preflight.py` with a structured helper that runs module validation and returns deterministic status payload.
- [x] 1.2 Implement one-attempt remediation branch: when `reference_integrity.failed > 0`, run monster reference closure once, then re-run validation.
- [x] 1.3 Ensure helper returns explicit terminal states (`pass`, `repaired_pass`, `fail`) with actionable message text for fail state.

## 2. Start-Game Hook Wiring

- [x] 2.1 Update `handle_start_game()` in `web/web_interface.py` to call the new helper before launching the game thread.
- [x] 2.2 Preserve current hard-fail behavior for unresolved references after remediation and emit deterministic `[SYSTEM]` operator message.
- [x] 2.3 Keep host-file changes minimal and mark integration points with `# TABLETOP MODE:`.

## 3. Regression Coverage

- [x] 3.1 Add regression tests for helper outcomes: direct pass, remediation pass, remediation fail.
- [x] 3.2 Add regression test ensuring remediation runs at most once per start-game preflight call.
- [x] 3.3 Add regression test ensuring startup blocks when post-remediation unresolved references remain.

## 4. Verification

- [x] 4.1 Run `python3 -m py_compile web/extensions/start_game_preflight.py web/web_interface.py`.
- [x] 4.2 Run targeted start-game preflight regression tests added in this change.
- [x] 4.3 Run `.venv/bin/python core/validation/validate_module_files.py --module The_Thornwood_Watch` and confirm reference-integrity remains pass.
- [x] 4.4 Run `openspec validate start-game-monster-preflight-hard-fail`.
