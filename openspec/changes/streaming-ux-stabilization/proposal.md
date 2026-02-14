## Why

Initial streaming rollout improved responsiveness in some paths but exposed several UX and lifecycle defects during live tabletop testing:

- Raw JSON token leakage (`{`, `\n`, escaped fragments) is visible during draft streaming.
- Final committed narration can be rendered again as a second block, causing duplicate DM output.
- Startup behavior is inconsistent between injected-return and normal-start paths.
- Stream sentence TTS can over-queue and churn under rapid deltas.

These issues reduce trust in narration quality and make live session pacing worse than the non-stream fallback path. We need a stabilization change that preserves the streaming architecture while enforcing clean player-facing output and deterministic commit behavior.

## What Changes

- Add a narration-safe streaming policy that prevents raw JSON/control-plane tokens from being rendered to player chat.
- Add per-turn render deduplication so committed narration does not appear twice.
- Align startup narration behavior across injected-return and normal-start flows under the same streaming policy.
- Add bounded stream TTS queue policy to prevent queue overflow/churn and stale playback.
- Preserve compatibility with existing `status_update`, `game_output`, and manual/API TTS controls.

## Capabilities

### New Capabilities
- `narration-stream-sanitization`: ensure streamed draft output is player-safe narration content only.
- `stream-commit-dedup`: enforce one canonical rendered narration per completed turn.
- `startup-stream-consistency`: unify startup narration behavior across startup branches.
- `stream-tts-queue-policy`: bound and stabilize sentence-level TTS during active stream attempts.

### Modified Capabilities
- `narration-streaming-pipeline`: tighten draft rendering contract and startup integration semantics.
- `stream-retry-commit-lifecycle`: extend commit/supersede semantics with render dedupe guarantees.
- `browser-tts-stream-sync`: add bounded queue behavior and stale-fragment suppression rules.

## Impact

- Affected code:
  - `main.py`
  - `core/managers/combat_manager.py`
  - `web/extensions/streaming_events.py`
  - `web/web_interface.py`
  - `web/templates/game_interface.html`
  - `web/static/js/tts_queue_manager.js`
- Affected behavior:
  - Player-facing stream rendering, startup narration path selection, and stream sentence TTS pacing.
- Risk:
  - Medium; changes are localized to streaming/display lifecycle and should not alter mechanical state handling.
- Rollback:
  - Disable `ENABLE_CHAT_STREAMING` and `ENABLE_BROWSER_TTS_STREAM_SYNC` to return to stable batch narration path.
