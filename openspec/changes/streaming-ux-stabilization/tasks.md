## 1. Stream Sanitization and Canonical Render Contract

- [x] 1.1 Implement narration-safe stream draft emission for JSON-mode generation so raw control-plane tokens are not rendered.
- [x] 1.2 Add per-turn dedupe guard to prevent duplicate final block narration after stream commit.
- [x] 1.3 Ensure superseded attempts cannot become canonical visible output.
- [x] 1.4 Verify narrative compile path: `python3 -m py_compile main.py`.

## 2. Startup Path Consistency

- [x] 2.1 Unify startup injected-return and normal-start branches under one streaming policy.
- [x] 2.2 Ensure startup canonical commit semantics match runtime turn semantics.
- [x] 2.3 Verify startup flow still works with streaming disabled fallback.

## 3. Stream TTS Queue Stabilization

- [x] 3.1 Enforce bounded pending sentence queue for stream TTS while playback is active.
- [x] 3.2 Ensure supersede clears stale queued fragments and cancels stale playback.
- [x] 3.3 Preserve manual/API TTS paths and `skipTTS` semantics.

## 4. Validation and Regression Coverage

- [x] 4.1 Add automated checks for no raw JSON leakage in player-facing stream drafts.
- [x] 4.2 Add automated checks for single canonical render per accepted turn.
- [x] 4.3 Add startup branch parity checks for streaming policy.
- [x] 4.4 Add stream TTS queue boundedness checks under rapid deltas.
- [ ] 4.5 Run smoke matrix for SP/MP with streaming on/off in narrative and combat paths.
- [x] 4.6 Run compile/test baseline: `python3 -m py_compile main.py core/managers/combat_manager.py web/web_interface.py` and `python3 scripts/test_multi_pc_combat.py`.
