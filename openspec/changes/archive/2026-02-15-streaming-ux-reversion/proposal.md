## Why

The current streaming UX implementation exposes control-plane JSON token deltas directly in player chat during generation. In live play this produces noisy output (`{}`, `\n`, partial JSON fragments), causes duplicate narration presentation (draft stream followed by canonical block output), and degrades stream TTS quality.

For tabletop sessions, clean narration and predictable turn pacing are more important than draft token visibility. We need a formal rollback to the stable block-output path while preserving the OpenSpec history of the streaming experiment.

## What Changes

- Revert player-facing narration streaming behavior to block-output-only rendering.
- Disable stream sentence-level TTS synchronization and retain existing manual/API TTS behavior on final narration blocks.
- Preserve canonical narration path through existing JSON parsing/validation and `game_output` emission.
- Keep a minimal `stream=true` foundation in code for future implementation:
  - feature flags in `model_config.py` (disabled by default),
  - backend lifecycle helper in `web/extensions/streaming_events.py`,
  - minimal transport/template wiring in `web/web_interface.py`.
- Remove rollback-external execution hooks from `web/web_interface.py` that suppress canonical narration at output-capture time; keep only transport + flag pass-through.

## Capabilities

### New Capabilities
- `streaming-disabled-stable-output`: enforce stable non-stream narration rendering in web UX.
- `tts-block-narration-only`: ensure TTS operates on canonical block narration rather than stream drafts.
- `canonical-output-single-path`: maintain one user-visible narration path per turn.

### Modified Capabilities
- `narration-streaming-pipeline`: revert default runtime behavior to disabled/non-player-facing mode.
- `browser-tts-stream-sync`: disable stream sentence sync in runtime path.
- `stream-retry-commit-lifecycle`: retain control-plane semantics without draft UI exposure.

## Impact

- Affected code:
  - Keep foundation: `model_config.py`, `web/extensions/streaming_events.py`, `web/web_interface.py`
  - Revert execution: `main.py`, `core/managers/combat_manager.py`, `web/templates/game_interface.html`, `web/static/js/tts_queue_manager.js`
- Runtime behavior:
  - Web users receive only canonical block narration output.
  - Stream draft events no longer drive chat/TTS UX.
  - Backend stream helper may remain present but dormant while flags are disabled.
  - `web_interface` output capture behavior remains baseline (no stream-dedupe suppression hook active).
- Risk:
  - Low-medium; rollback targets streaming UX path only, leaving mechanics and validation intact.
- Rollback of this rollback:
  - Re-enable streaming flags and reintroduce draft rendering only after narration-safe stream extraction redesign.
