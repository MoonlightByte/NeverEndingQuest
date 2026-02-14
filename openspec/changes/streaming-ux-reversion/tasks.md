## 0. Keep vs Revert Selection

- [x] 0.1 Keep OpenSpec history directories:
  - `openspec/changes/streaming-ux-dual-pipeline/`
  - `openspec/changes/streaming-ux-stabilization/`
  - `openspec/changes/streaming-ux-reversion/`
- [x] 0.2 Keep foundation module: `web/extensions/streaming_events.py`.
- [x] 0.3 Keep streaming flags in `model_config.py` with defaults OFF.
- [x] 0.4 Keep only minimal host wiring in `web/web_interface.py`:
  - transport setup (`configure_stream_transport(socketio.emit)`),
  - template flag pass-through (`ENABLE_CHAT_STREAMING`, `ENABLE_BROWSER_TTS_STREAM_SYNC`).
- [x] 0.5 Revert `web/web_interface.py` execution hook usage in `WebOutputCapture`:
  - remove `should_suppress_canonical_narration` import,
  - remove suppression checks around canonical narration emit paths.
- [x] 0.6 Revert narrative execution integration in `main.py` (startup and turn retry stream lifecycle).
- [x] 0.7 Revert combat execution integration in `core/managers/combat_manager.py` (stream attempt/commit/supersede lifecycle).
- [x] 0.8 Revert draft stream chat rendering and stream sentence TTS pipeline in `web/templates/game_interface.html`.
- [x] 0.9 Revert stream-source queue behavior in `web/static/js/tts_queue_manager.js` (sourceTag/maxPending/cancelBySourceTag for draft streams).

## 1. Runtime Rollback Outcome

- [ ] 1.1 Confirm runtime behavior is block-output-only narration in startup, narrative turns, and combat turns.
- [ ] 1.2 Confirm no raw JSON token leakage (`{}`, `\\n`, escaped fragments) appears in player chat.
- [ ] 1.3 Confirm no duplicate draft + canonical narration output appears for the same turn.
- [ ] 1.4 Confirm manual/API TTS still works for canonical block narration messages.

## 2. Validation and Regression

- [x] 2.1 Compile-check rollback-affected modules.
- [x] 2.2 Run `python3 scripts/test_multi_pc_combat.py`.
- [x] 2.3 Run targeted streaming sanity tests (foundation dormant with flags OFF).
- [ ] 2.4 Manual smoke: intro + one non-combat turn + one combat round.
