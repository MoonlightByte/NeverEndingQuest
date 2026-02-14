## Context

The streaming rollout introduced a draft narration channel intended to improve perceived latency. In practice, model output is JSON-first, so token streaming to chat displayed control-plane artifacts and produced poor TTS behavior. Canonical narration still arrives through parsed/validated block output, which is the stable path used before streaming.

This change rolls player-facing UX back to canonical block output while preserving a thin backend foundation for future stream-safe redesign.

## Goals / Non-Goals

**Goals**
- Restore clean player-facing narration with no JSON token leakage.
- Ensure one visible narration output path per turn.
- Keep existing action validation/state-update pipeline unchanged.
- Keep manual/API TTS functionality intact.

**Non-Goals**
- No redesign of provider streaming internals.
- No removal of OpenSpec artifacts from prior streaming work.
- No combat mechanics, initiative, or schema changes.

## Decisions

### Decision 1: Keep foundation, revert execution

Choice:
- Keep disabled feature flags and streaming helper/transport scaffolding in place.
- Remove/disable runtime execution paths that surface draft stream tokens to players.
- Force non-stream call behavior in narrative and combat runtime paths.

Rationale:
- Preserves future implementation runway without carrying current UX risk.

### Decision 2: Keep canonical block narration as sole user-visible path

Choice:
- Preserve existing `game_output` narration rendering.
- Stream draft events are not used for chat UI rendering in rollback mode.

Rationale:
- Stable, validated, and already integrated with live monitor and cache behavior.

### Decision 3: Keep TTS on canonical narration only

Choice:
- Disable stream sentence queue path.
- Preserve manual/API TTS controls for final narration blocks.

Rationale:
- Avoid queue overflow and stale fragment speech from draft attempts.

### Decision 4: Preserve merge-safe boundaries for future streaming return

Choice:
- Keep host-file changes minimal and clearly marked `# TABLETOP MODE:`.
- Keep stream helper encapsulated under `web/extensions/streaming_events.py`.

Rationale:
- Supports upstream merge hygiene and controlled future re-entry.

### Decision 5: Keep `web_interface` foundation minimal

Choice:
- Keep only stream transport setup (`configure_stream_transport`) and template feature-flag pass-through in `web/web_interface.py`.
- Revert any `WebOutputCapture` suppression logic that conditionally drops canonical narration based on stream helper state.

Rationale:
- Prevents hidden output-path coupling while still preserving backend foundation hooks.

## Risks / Trade-offs

- Loss of perceived incremental typing effect.
  - Accepted in favor of reliable storytelling UX.
- Streaming scaffolding remains in codebase.
  - Accepted to preserve auditability and future redesign option.

## Validation Plan

- Compile checks on `main.py`, `core/managers/combat_manager.py`, `web/web_interface.py`.
- Regression tests: `scripts/test_multi_pc_combat.py` and `scripts/test_streaming_ux_stabilization.py` (should still pass where applicable, with stream paths disabled).
- Manual smoke:
  - Start game intro should display only block narration.
  - No visible `{}`/`\n` stream leakage.
  - TTS should narrate canonical block text only.
  - Confirm dormant foundation does not alter behavior when flags are disabled.
  - Confirm `WebOutputCapture` emits canonical narration without stream suppression hooks.
