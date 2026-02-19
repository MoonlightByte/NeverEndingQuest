# Streaming UX Implementation Plan (Revised for Current SP/MP Code)

## Objective

Implement web-only token streaming for player-facing narration in narrative and combat flows, while preserving existing validation, retry, and action-application behavior. Reuse current status/input lock behavior and keep terminal mode unchanged.

## Why this revision

The previous plan was good conceptually, but this revision aligns directly to existing functions and extension boundaries:

- Narrative generation path: `main.py:get_ai_response()` and main-loop validation in `main.py`.
- Combat generation path: `core/managers/combat_manager.py:run_combat_simulation()`.
- Web transport path: `web/web_interface.py` (SocketIO events, queues, cached messages).
- Existing marker and TTS behavior: `web/output_markers.py`, `web/templates/game_interface.html`, `web/static/js/tts_queue_manager.js`.

## Scope

In scope:
- Token streaming for narration text only (web UI).
- Draft/supersede/commit lifecycle tied to current retry loops.
- Status channel continuity using current `status_update` path.
- Browser `speechSynthesis` sentence sync for stream mode.

Out of scope:
- Streaming validator output to chat.
- Replacing existing OpenAI TTS button/manual path.
- Full LLM router migration.
- Terminal-mode streaming.

## Current system realities to preserve

1. Output buffering and message cache
- Current player chat rendering relies on `game_output` and `addMessage(...)`.
- `WebOutputCapture` currently emits complete narration chunks and marker parsing (`[skipTTS]`, `[prefill:...]`) through `extract_output_markers()`.

2. Retry-first validation architecture
- Narrative: generation -> validation -> retry loop in `main.py`.
- Combat: generation -> validation/integrity checks -> retry loop in `combat_manager.py`.
- Only final accepted response should become canonical history.

3. Existing status lock lane
- `status_update` already drives input disable/enable and placeholder text in UI.
- This must remain the primary control-plane channel.

4. SP/MP compatibility
- Tabletop mode metadata (`active_pc`, multi-PC initiative commands, combat phases) must remain untouched.
- Streaming must not alter command handling (`/init`, `/end`, `/att`, `/dmg`) or action schemas.

## Architecture

### A. Dual pipeline (unchanged principle, stricter integration)

1. Narration pipeline (player-facing)
- Stream token deltas to draft UI message.
- Final draft text is assembled server-side for validation.

2. Control pipeline (background)
- Validation, retries, action application, persistence.
- Status updates only via existing status manager callback path.

### B. New helper boundary (required)

Add a shared helper module:
- `web/extensions/streaming_events.py` (new)

Responsibilities:
- Start/delta/end/error event emission.
- Server-side full-text accumulation from token deltas.
- Stream ID / turn ID / attempt bookkeeping.
- No game logic, no validation decisions.

This keeps core SP/MP game logic in `main.py` and `combat_manager.py`, and keeps web transport concerns in web extensions.

### C. Web-only gating

Streaming is enabled only when all are true:
- `ENABLE_CHAT_STREAMING = True`
- running under web interface (SocketIO available)
- provider/callsite supports stream

Otherwise: current non-stream path remains the default.

## Event contract

### New socket events

1. `narration_stream_start`
- `streamId`, `turnId`, `mode` (`narrative` or `combat`), `attempt`, `character` (optional), `skipTTS` (optional).

2. `narration_stream_delta`
- `streamId`, `turnId`, `seq`, `text`.

3. `narration_stream_end`
- `streamId`, `turnId`, `attempt`, `fullText`.

4. `narration_stream_superseded`
- `streamId`, `turnId`, `supersededByStreamId` (optional), `reason`.

5. `narration_stream_commit`
- `streamId`, `turnId`, `attempt`, `committedText`.

6. `narration_stream_error`
- `streamId`, `turnId`, `error`.

### Existing events retained

- `status_update`: unchanged control-plane source of truth.
- `game_output`: fallback path and compatibility path.

## Message lifecycle rules

Per turn:
1. queued
2. streaming
3. finalizing (generation done, validation pending)
4. validating
5. terminal: committed or superseded or error

Rules:
- Input lock remains tied to existing status state.
- Each attempt has exactly one draft stream.
- Only committed attempt is canonical.
- Superseded attempts never persist to canonical history.

## Backend implementation plan

### Phase 1 - Shared stream helper and narrative integration

Files:
- `web/extensions/streaming_events.py` (new)
- `main.py`
- `web/web_interface.py`

Tasks:
1. Create helper API for emitting stream events and collecting full text.
2. Integrate helper into `get_ai_response()` generation call path.
3. Keep existing provider fallback logic intact (do not fork model-selection logic).
4. If stream unsupported or fails, transparently fall back to current non-stream generation.

### Phase 2 - Narrative retry/supersede/commit coupling

Files:
- `main.py`

Tasks:
1. Tie stream attempt IDs to existing retry loop (`retry_count`).
2. Emit `narration_stream_superseded` before each retry attempt.
3. Emit `narration_stream_commit` only when validation succeeds.
4. Preserve existing validation error-note behavior in conversation history.

### Phase 3 - Combat integration (staged)

Files:
- `core/managers/combat_manager.py`
- `web/extensions/streaming_events.py`

Tasks:
1. Integrate stream helper for combat narration generation attempts.
2. Keep all current combat validation and integrity checks unchanged.
3. Emit supersede/commit aligned to existing combat retry loop.
4. Ensure initiative gate behavior remains unchanged.

### Phase 4 - Status hardening

Files:
- `core/managers/status_manager.py`
- `main.py`
- `core/managers/combat_manager.py`

Tasks:
1. Standardize status strings for generation/finalizing/validation/retry.
2. Add `StatusTimer` only around long-running callsites.
3. Do not add new parallel status channels.

## Frontend implementation plan

### Phase 1 - Draft stream renderer

File:
- `web/templates/game_interface.html`

Tasks:
1. Add handlers for start/delta/end/superseded/commit/error.
2. Maintain `activeStreams` keyed by `streamId`.
3. Render draft text in stable message node without breaking current `addMessage()` fallback path.
4. Ensure reconnect/idempotency logic ignores stale sequence deltas.

### Phase 2 - Browser TTS stream sync

Files:
- `web/templates/game_interface.html`
- `web/static/js/tts_queue_manager.js` (or new focused stream TTS helper if cleaner)

Tasks:
1. Add per-stream sentence buffering for `speechSynthesis`.
2. Trigger speech on sentence boundaries (`.`, `!`, `?`, newline).
3. Cancel queued/stale sentence fragments on supersede.
4. Keep manual button playback behavior untouched.
5. Honor `skipTTS` and current system/mechanical content filters.

Note:
- Existing queue manager is designed around `playTTS` audio flow. Stream TTS may require a separate lightweight queue for `speechSynthesisUtterance` to avoid cross-coupling.

## Observability and compatibility

1. Cached messages
- Preserve current cache behavior. Committed narration should still be cacheable and replay-safe.

2. Live chat monitor
- Ensure final committed narration still reaches existing monitor expectations (currently logs on `game_output` events).
- If committed stream does not emit `game_output`, extend monitor to consume commit event explicitly.

3. Marker behavior
- Continue honoring `[skipTTS]` and `[prefill:...]` semantics for compatible paths.
- Do not regress current mechanical-message suppression.

## Feature flags

Add in configuration:
- `ENABLE_CHAT_STREAMING = True`
- `ENABLE_BROWSER_TTS_STREAM_SYNC = True`
- `STREAM_SUPERSEDED_VISIBLE = False`

Rules:
- Default safe fallback is non-streaming.
- Terminal mode always non-streaming.

## Rollout order

1. Narrative web happy path (no retries).
2. Narrative web retries with supersede/commit.
3. Combat opening narration only.
4. Full combat turn retries.
5. Optional monitor/status refinements.

## Testing plan

### Functional
- Stream starts quickly and updates incrementally.
- Input lock remains active until terminal state.
- Failed attempt visibly supersedes and retry begins cleanly.
- Committed text matches persisted history text.

### SP/MP behavior
- Single-player conversation unchanged when streaming disabled.
- Multi-PC active character context remains correct.
- Combat phase commands and initiative behavior unchanged.

### TTS
- Chrome/Edge sentence playback is ordered and non-overlapping.
- Superseded drafts do not continue speaking stale text.
- Existing manual TTS button still works.

### Regression commands

```bash
python3 -m py_compile web/web_interface.py main.py core/managers/combat_manager.py web/extensions/streaming_events.py
python3 scripts/test_multi_pc_combat.py
```

## Risks and mitigations

1. Draft and committed mismatch
- Mitigation: strict supersede/commit lifecycle, persist committed only.

2. Event races or duplicate deltas
- Mitigation: sequence numbers, idempotent handlers, stale stream guard.

3. Provider streaming incompatibility
- Mitigation: capability check + immediate fallback to batch path.

4. TTS stale fragments
- Mitigation: sentence queue with per-stream cancel semantics.

5. Combat-loop complexity
- Mitigation: narrative-first rollout, then combat.

## Definition of done

- Web chat supports token streaming in narrative and combat paths.
- Validation and retry logic remain mechanically correct and unchanged in principle.
- Status channel remains the sole input-lock control path.
- Browser stream TTS works sentence-by-sentence with stale-cancel safety.
- Feature flags provide immediate rollback to current behavior.
