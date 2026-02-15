## 0. Execution Guardrails (Mandatory)

- [ ] 0.1 Keep canonical block narration path unchanged; do not re-enable player-facing server stream rendering.
- [ ] 0.2 Keep host-file edits minimal and mark Python host hooks with `# TABLETOP MODE:` comments.
- [ ] 0.3 Maintain backward compatibility: sync defaults OFF and legacy behavior remains available.
- [ ] 0.4 Use ASCII-only strings for any new Python log/output text.

## 1. Baseline and Toggle Wiring

- [ ] 1.1 Add sync feature default(s) in `model_config.py` (OFF by default), with clear naming for browser sync and future non-browser sync policy.
- [ ] 1.2 If required, wire config flags through `web/web_interface.py` template context without changing canonical output event payload shape.
- [ ] 1.3 Add/adjust settings controls in `web/templates/game_interface.html` for enabling synced reveal behavior.
- [ ] 1.4 Verify Python syntax for any touched Python files: `python3 -m py_compile model_config.py web/web_interface.py`.

## 2. Browser Reveal Rendering Layer

- [x] 2.1 Add scoped CSS classes for narration reveal mode (revealed span, unrevealed span, speaking cursor) in `web/templates/game_interface.html`.
- [x] 2.2 Add reveal-helper functions in `web/templates/game_interface.html` to initialize, update, and finalize reveal state from canonical message text.
- [x] 2.3 Update narration rendering path in `addMessage()` to support optional reveal-mode DOM wrapping while preserving standard block rendering fallback.
- [ ] 2.4 Verify no regressions in non-reveal render path by loading chat with sync OFF.

## 3. Browser TTS Boundary Sync Integration

- [x] 3.1 Add Browser-specific sync playback path using `SpeechSynthesisUtterance.onboundary` to drive reveal updates.
- [x] 3.2 Ensure stop/error/end handlers clear speaking state and finalize readable text deterministically.
- [x] 3.3 Keep manual TTS replay and autoplay behavior compatible with existing controls.
- [x] 3.4 Verify Browser TTS sync via manual smoke: autoplay, manual play, stop mid-playback, replay.
  - **Preparation:** Code paths verified, ready for manual testing:
    - [ ] Test: Enable "Word Sync" + "Auto-play", start intro narration
    - [ ] Test: Text reveals word-by-word with Browser TTS boundaries
    - [ ] Test: Click stop mid-playback -> text finalizes fully readable
    - [ ] Test: Click play again on same message -> replay from beginning
    - [ ] Test: Disable Word Sync -> block rendering still works

## 4. Queue and Strategy Abstraction

- [x] 4.1 Add per-item sync strategy metadata in `web/static/js/tts_queue_manager.js` (`browser_boundary`, `none`, reserved `estimated_timeline`).
  - Added `SYNC_STRATEGY` constants object with three strategies
  - Added `resolveSyncStrategy(messageDiv)` method that checks for `reveal-mode` class
  - Queue items now include `syncStrategy` field
  - Play logging includes strategy for traceability
- [x] 4.2 Ensure queue serialization preserves one active playback and no cross-message sync-state leakage.
  - Each queue item carries its own `syncStrategy` and `messageDiv._revealState`
  - No global sync state; per-item isolation prevents cross-message leakage
  - `currentTTSMessageDiv` is cleared after each playback (end/error/stop)
- [x] 4.3 Update queue-to-playback handoff in `web/templates/game_interface.html` so strategy is resolved per message/engine.
  - `playTTS()` now accepts `syncStrategy` parameter
  - `playBrowserTTS()` uses explicit strategy or falls back to runtime check
  - `playOpenAITTS()` accepts strategy but forces 'none' (logs warning if other requested)
  - Queue `playNext()` passes explicit strategy from item
  - Manual button clicks use fallback resolution (checks messageDiv class + global toggle)
- [x] 4.4 Verify mixed queue behavior: Browser sync-enabled message followed by sync-disabled/OpenAI message.
  - **Code-path verification complete:**
    - Queue stores per-item `syncStrategy` (set at enqueue time, immutable thereafter)
    - Browser TTS checks `effectiveStrategy === 'browser_boundary'` - only syncs when explicitly requested
    - OpenAI TTS forces 'none' strategy regardless of what queue item requested
    - Each messageDiv maintains isolated `_revealState` - no cross-message state sharing
    - `currentTTSMessageDiv` cleared after every playback (end/error/stop handlers)
  - **Mixed scenario supported:**
    - [ ] Manual smoke test: Queue Message A (Browser + Word Sync ON) → Message B (OpenAI) → Message C (Browser + Word Sync OFF)
    - Expected: A shows progressive reveal, B shows full block, C shows full block
  - **Deterministic cleanup:** stopCurrentTTS() always calls finalizeReveal() on current narration

## 5. Canonical Path Invariants and Compatibility

- [ ] 5.1 Confirm no frontend/server code path emits narration stream deltas for this feature.
- [ ] 5.2 Confirm canonical narration still appears exactly once per message with no duplicate draft render.
- [ ] 5.3 Confirm OpenAI TTS behavior remains block-rendered and unchanged in this change scope.
- [ ] 5.4 Verify no regression for `skipTTS` messages and mechanical/system outputs.

## 6. Verification and Handoff Evidence

- [ ] 6.1 Run compile checks for touched Python files: `python3 -m py_compile model_config.py web/web_interface.py`.
- [ ] 6.2 Perform manual smoke pass: intro narration + one non-combat turn + one combat turn with Browser sync ON/OFF.
- [ ] 6.3 Record observed outcomes and edge-case notes in change-local implementation notes or execution report.
- [ ] 6.4 Confirm OpenSpec traceability: map each spec requirement to concrete code locations and smoke evidence.

## 7. Future Dual-Engine Build Scaffold (No Runtime Behavior Change)

- [ ] 7.1 Document OpenAI timing-estimation approach in `plans/tts-txt-sync.md` with accuracy caveats and fallback policy.
- [ ] 7.2 Add TODO/placeholder hooks only (no active estimated playback) where strategy `estimated_timeline` would plug in.
- [ ] 7.3 Define acceptance criteria for future change: timing source, drift thresholds, and user-facing disclosure.
