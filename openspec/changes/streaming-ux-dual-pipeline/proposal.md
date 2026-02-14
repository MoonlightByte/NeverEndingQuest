## Why

Narration currently appears only after full model completion, which increases perceived latency and makes long responses feel unresponsive in web play. We need streaming now to improve responsiveness while preserving existing validation/retry safety and SP/MP mechanical correctness.

## What Changes

- Add a web-only narration streaming pipeline that emits token deltas for draft rendering while keeping validation and action application in the control plane.
- Add explicit draft lifecycle semantics (`start`, `delta`, `end`, `superseded`, `commit`, `error`) so retries remain deterministic and understandable.
- Add shared backend stream transport helper in a web extension module to avoid duplicating streaming logic across narrative and combat callsites.
- Add browser sentence-level TTS synchronization for streamed narration using `speechSynthesis`, with stale-cancel behavior on supersede.
- Preserve existing non-stream fallback path and feature flags for rapid rollback.
- Explicit non-goals for this change:
  - No streaming of validator output to player chat.
  - No replacement of existing manual/OpenAI TTS button behavior.
  - No full OpenRouter router migration or model-policy redesign.
  - No changes to combat command semantics (`/init`, `/end`, `/att`, `/dmg`) or action schema contracts.

## Capabilities

### New Capabilities
- `narration-streaming-pipeline`: Web-only token streaming transport and event contract for narrative and combat narration drafts.
- `stream-retry-commit-lifecycle`: Deterministic supersede/commit behavior coupled to existing validation retry loops.
- `browser-tts-stream-sync`: Sentence-buffered browser TTS synchronization for streamed narration with queue safety.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `main.py` (narrative generation integration)
  - `core/managers/combat_manager.py` (combat generation integration)
  - `web/web_interface.py` and `web/templates/game_interface.html` (socket and UI handling)
  - `web/extensions/streaming_events.py` (new helper module)
- APIs/events: introduces new SocketIO narration stream events while preserving `status_update` and `game_output` compatibility paths.
- Dependencies/systems: reuses current provider factory and retry handling; no new external dependency required.
- Rollout risk: medium-high due to interaction with existing retry-heavy combat and narration loops; mitigated by staged rollout (narrative first, combat second) and feature flags.
- Fallback strategy: if stream unsupported/fails at runtime, immediately use current batch response path and continue normal validation workflow.
- Provider outage/quota behavior: preserve existing provider error handling and fallback behavior; streaming path must degrade cleanly without orphaning input lock state.
- Merge-safety/SP-MP impact: keep host-file edits minimal and marked, prefer extension-module implementation, preserve single-player compatibility and multi-PC combat phase behavior.

## Rollout Checklist and Rollback

- Enable `ENABLE_CHAT_STREAMING` in a local test session and verify draft start/delta/end/commit events in browser devtools.
- Verify retry behavior by forcing a validation failure and confirming superseded draft handling.
- Verify SP and MP combat flows still enforce `/init`, `/end`, `/att`, and `/dmg` semantics.
- Verify `status_update` remains the only input lock controller during long generation/retry paths.
- Verify TTS behavior for stream commit/supersede while manual TTS buttons remain available.

Rollback procedure:
- Set `ENABLE_CHAT_STREAMING = False` and `ENABLE_BROWSER_TTS_STREAM_SYNC = False`.
- Restart web server; narration returns to `game_output`-only behavior without code rollback.
