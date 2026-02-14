## 1. Streaming Foundation and Event Transport

- [x] 1.1 Add `web/extensions/streaming_events.py` with helpers for `start/delta/end/error/superseded/commit` emission and server-side full-text accumulation.
- [x] 1.2 Add streaming feature flags to configuration (`ENABLE_CHAT_STREAMING`, `ENABLE_BROWSER_TTS_STREAM_SYNC`, `STREAM_SUPERSEDED_VISIBLE`) with safe defaults and no behavior change when disabled.
- [x] 1.3 Add minimal `# TABLETOP MODE:` host hook wiring in `web/web_interface.py` to expose stream transport helpers without altering existing `game_output` fallback path.
- [x] 1.4 Verify foundation compiles: `python3 -m py_compile web/web_interface.py web/extensions/streaming_events.py`.

## 2. Narrative Path Integration

- [x] 2.1 Integrate streaming generation path in `main.py:get_ai_response()` behind `ENABLE_CHAT_STREAMING`, preserving current provider fallback behavior.
- [x] 2.2 Couple stream attempt lifecycle to narrative retry loop in `main.py` (`superseded` on retry, `commit` on validation success).
- [x] 2.3 Preserve canonical history rule so only committed narration is persisted as accepted output.
- [x] 2.4 Verify narrative path compiles and fallback behavior remains available: `python3 -m py_compile main.py`.

## 3. Combat Path Integration

- [x] 3.1 Integrate streaming generation in `core/managers/combat_manager.py` retry loop behind `ENABLE_CHAT_STREAMING`.
- [x] 3.2 Preserve existing combat validation/integrity checks and initiative command semantics while adding supersede/commit event coupling.
- [x] 3.3 Ensure terminal failure paths do not deadlock status/input state.
- [x] 3.4 Verify combat path compiles and baseline tests run: `python3 -m py_compile core/managers/combat_manager.py` and `python3 scripts/test_multi_pc_combat.py`.

## 4. Frontend Draft Rendering and Stream TTS Sync

- [x] 4.1 Add stream event handlers in `web/templates/game_interface.html` with `activeStreams` map, ordered delta application, and stale sequence guards.
- [x] 4.2 Implement draft message UI behavior for superseded and committed attempts while preserving existing `addMessage()` fallback handling.
- [x] 4.3 Implement sentence-buffered stream TTS sync in frontend (or a focused helper) with stale-cancel behavior on supersede.
- [x] 4.4 Preserve existing manual/API TTS controls and `skipTTS` suppression semantics.

## 5. Observability, Compatibility, and Rollout Validation

- [x] 5.1 Ensure committed narration remains compatible with cached message replay and live chat monitor expectations.
- [x] 5.2 Validate status channel remains sole input lock authority during streaming, validation, retry, and terminal states.
- [x] 5.3 Run end-to-end smoke checks for narrative and combat in both SP and MP with streaming on and off.
- [x] 5.4 Record rollout checklist and rollback procedure in change notes before implementation completion.
