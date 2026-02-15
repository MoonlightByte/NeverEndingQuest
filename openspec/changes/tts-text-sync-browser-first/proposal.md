## Why

The current narration UX shows full DM text instantly, then plays TTS, which feels like two separate phases instead of one live storytelling stream. We want a browser-safe, merge-safe improvement that syncs visible text progression to speech timing without reintroducing unstable server streaming behavior.

## What Changes

- Add browser-TTS word-boundary synchronized text reveal for narration messages (`SpeechSynthesisUtterance.onboundary` driven).
- Keep canonical block output as the source of truth (no server token streaming, no draft JSON rendering path).
- Add a client-side sync engine abstraction so Browser TTS can run in precise mode now and OpenAI TTS can plug in later via estimated timing mode.
- Add explicit fallback behavior: if boundary events are unavailable, reveal degrades to current block rendering with normal TTS playback.
- Add operator-facing docs and Kimi/GLM execution prompts for phased implementation.

### Non-goals

- No re-enable of server-side narration stream events or draft token rendering.
- No change to LLM generation pipeline, retry policy, or canonical output capture path.
- No change to game mechanics, combat state logic, or persistence formats.
- No immediate OpenAI TTS timing-estimation rollout in this change (foundation only).

## Capabilities

### New Capabilities
- `tts-browser-word-sync`: Precise text reveal synchronized to Browser TTS word boundaries for narration messages.
- `tts-sync-engine-abstraction`: Client-side sync strategy boundary that supports browser-precise mode now and non-browser timing-estimate mode later.

### Modified Capabilities
- `tts-block-narration-only`: Clarify that canonical block narration remains the only source path while client-side progressive reveal may be applied during TTS playback.

## Impact

- Affected code:
  - `web/templates/game_interface.html`
  - `web/static/js/tts_queue_manager.js`
  - `web/web_interface.py` (only if feature flag/template wiring is needed)
  - `model_config.py` (optional feature flag default OFF)
  - `plans/tts-txt-sync.md`
- User-visible behavior:
  - Browser TTS users can opt into synchronized word-by-word narration reveal.
  - Existing block output and TTS behavior remains unchanged when feature is disabled.
  - OpenAI TTS remains block-rendered in this change, with documented future extension path.
- Merge safety and compatibility:
  - Host file changes remain minimal and marked with `# TABLETOP MODE:` where applicable.
  - Single-player and tabletop multiplayer flows remain backward compatible.
- Rollout risk and fallback:
  - Primary risk is browser variance in `onboundary` behavior.
  - Fallback is deterministic: disable feature toggle or auto-degrade to current block display path.
