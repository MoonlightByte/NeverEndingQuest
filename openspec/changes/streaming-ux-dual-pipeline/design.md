## Context

NeverEndingQuest currently delivers narration to web clients as complete messages after blocking LLM calls finish. This creates visible latency in both narrative and combat turns even when the model is actively producing text. The current architecture already has strong control-plane behavior (status lock, validation retries, action application) and must not be regressed.

Current boundaries that matter:
- Generation and validation orchestration lives in `main.py` and `core/managers/combat_manager.py`.
- Web transport and output capture lives in `web/web_interface.py`.
- Frontend message rendering and TTS behavior lives in `web/templates/game_interface.html` and `web/static/js/tts_queue_manager.js`.
- Marker semantics (`[skipTTS]`, `[prefill:...]`) live in `web/output_markers.py`.

Key constraints:
- Preserve SP and MP behavior, especially multi-PC combat phase gating and existing retry loops.
- Preserve upstream merge safety by preferring extension modules and minimal host hooks marked `# TABLETOP MODE:`.
- Keep Python mechanical state as truth source; streaming affects UX only, not mechanics.

## Goals / Non-Goals

**Goals:**
- Provide web-only token streaming for narration drafts in narrative and combat paths.
- Preserve existing validation/retry/action-application control flow.
- Add deterministic supersede/commit lifecycle so draft text cannot become canonical unless validated.
- Keep status manager as the single input lock/unlock control path.
- Add browser sentence-synced stream TTS without breaking existing manual/API TTS controls.

**Non-Goals:**
- No streaming of validator feedback into player chat.
- No replacement of existing `game_output` fallback behavior.
- No changes to action schema contracts or combat command semantics.
- No model routing policy redesign.
- No terminal-mode streaming.

## Decisions

### Decision 1: Introduce a dedicated stream transport helper module

Choice:
- Add `web/extensions/streaming_events.py` to own stream event emission and stream text accumulation.

Rationale:
- Keeps transport concerns out of `main.py` and `combat_manager.py` business logic.
- Maintains plugin-style extension boundary and merge safety.
- Reduces duplicated stream bookkeeping across narrative and combat callsites.

Alternative considered:
- Embed streaming logic directly in each callsite.
- Rejected due to duplication and high regression risk in already complex combat loop.

### Decision 2: Keep dual pipeline with strict commit semantics

Choice:
- Streaming is draft-only until validation passes.
- On validation failure, emit supersede and retry with a new stream attempt.
- Persist only committed text.

Rationale:
- Aligns with existing retry-first safety model.
- Prevents contradictory drafts from contaminating canonical conversation history.

Alternative considered:
- Persist first streamed output and patch later.
- Rejected because it violates existing correctness guarantees and makes rollback ambiguous.

### Decision 3: Preserve status manager as single control-plane authority

Choice:
- Continue using `status_update` for input lock/unlock and user processing feedback.
- Streaming events do not control input lock state directly.

Rationale:
- Existing frontend already trusts status channel for input state.
- Avoids race conditions from multiple lock controllers.

Alternative considered:
- Add lock/unlock semantics directly to stream events.
- Rejected due to duplicate authority and reconnect complexity.

### Decision 4: Web-only feature-gated rollout with transparent fallback

Choice:
- Add flags (`ENABLE_CHAT_STREAMING`, `ENABLE_BROWSER_TTS_STREAM_SYNC`, `STREAM_SUPERSEDED_VISIBLE`).
- If stream unsupported/fails, immediately revert to current non-stream generation path in the same turn.

Rationale:
- Safe incremental rollout.
- Preserves continuity during provider issues.

Alternative considered:
- Hard fail when stream is unavailable.
- Rejected as unacceptable for live tabletop sessions.

### Decision 5: Separate stream TTS queue concerns from existing API TTS queue semantics

Choice:
- Keep current `playTTS`/manual flow unchanged.
- Add sentence-buffered stream TTS behavior that can cancel stale queued fragments on supersede.

Rationale:
- Current queue manager is optimized for API-audio lifecycle; stream utterances need different cancellation granularity.

Alternative considered:
- Force all stream speech through current queue manager unchanged.
- Rejected due to stale-fragment risk and coupling with audio element lifecycle.

## Risks / Trade-offs

- [Draft text differs from committed text] -> Mitigation: mandatory `superseded` and `commit` events; canonical history uses committed text only.
- [Socket race/replay on reconnect] -> Mitigation: `streamId` + monotonic `seq`; idempotent frontend handlers; stale delta discard.
- [Provider stream incompatibility] -> Mitigation: capability check and immediate fallback to batch path.
- [Combat loop complexity regression] -> Mitigation: narrative-first rollout, then combat; no change to combat mechanics pipeline.
- [TTS speaks stale text after retry] -> Mitigation: per-stream sentence buffers and supersede cancellation.
- [Observability gaps] -> Mitigation: ensure committed output remains visible to existing cache and live monitor expectations.

## Migration Plan

1. Add stream helper extension and event contract without changing current batch behavior.
2. Integrate narrative generation stream path behind `ENABLE_CHAT_STREAMING`.
3. Couple supersede/commit semantics to narrative retry loop.
4. Add frontend draft renderer and idempotent stream handlers.
5. Add stream TTS sync behind `ENABLE_BROWSER_TTS_STREAM_SYNC`.
6. Integrate combat streaming path, preserving current validation and phase gating logic.
7. Harden status messages with existing `StatusTimer` for long operations.
8. Validate SP and MP regressions; keep rollback to batch path available by flag.

Rollback strategy:
- Disable streaming flags and continue current `game_output` batch behavior unchanged.

## Open Questions

- Should committed narration also emit a synthetic `game_output` narration event for cache/monitor compatibility, or should monitors subscribe directly to `narration_stream_commit`?
- Should superseded drafts be hidden by default or dimmed with reason text in production?
- Which callsites should be first to adopt `StatusTimer` escalation text to avoid noisy status churn?
