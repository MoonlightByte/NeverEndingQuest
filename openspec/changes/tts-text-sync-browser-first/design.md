## Context

This repo recently reverted player-facing stream execution paths and stabilized on canonical block narration output. The new UX goal must preserve that rollback guarantee while adding a stronger "live narration" feel.

Current constraints:
- Canonical narration remains emitted once via existing output-capture path.
- Browser TTS already plays narration via Web Speech API.
- TTS queue manager already serializes playback and prevents overlap.
- OpenAI TTS playback is audio-blob based and does not expose native word timing.

The design therefore favors a client-only reveal layer driven by TTS playback events, not server stream transport.

## Goals / Non-Goals

**Goals:**
- Add precise Browser TTS text reveal synchronized with spoken words.
- Preserve canonical block narration as source of truth and history output.
- Keep behavior fail-safe when boundary events are unavailable.
- Introduce a small sync strategy abstraction that supports future OpenAI-estimated timing mode without major rewrites.
- Keep merge-safe boundaries and avoid broad host-file restructuring.

**Non-Goals:**
- Reintroducing backend narration stream transport to the player UI.
- Changing LLM generation/validation/retry plumbing.
- Implementing and shipping OpenAI timing estimation in this change.
- Redesigning chat layout or TTS provider settings UX beyond minimal toggle wiring.

## Decisions

1. **Client-only reveal model (no server streaming)**
   - Decision: progressive text reveal is computed entirely in browser from already-received canonical text.
   - Rationale: keeps rollback guarantees and avoids prior stream leakage failure modes.
   - Alternative considered: server-side delta emission per token/word. Rejected due to known UX instability risk and higher plumbing complexity.

2. **Word-boundary authority for Browser TTS**
   - Decision: use `SpeechSynthesisUtterance.onboundary` (`charIndex`, `charLength`) as the authoritative reveal cursor.
   - Rationale: provides near-real-time alignment with minimal drift.
   - Alternative considered: timer-only simulation for all engines. Rejected for Browser mode because native boundary data is higher quality.

3. **Sync strategy abstraction in frontend**
   - Decision: introduce a small strategy boundary (e.g., `browser_boundary`, `estimated_timeline`, `none`) consumed by TTS queue/playback path.
   - Rationale: enables future OpenAI sync without entangling queue logic and rendering logic.
   - Alternative considered: hardcode Browser-only branch inline in `playTTS`. Rejected because it increases future refactor cost and regression risk.

4. **Feature gating and deterministic fallback**
   - Decision: feature defaults OFF and can be toggled; unsupported runtime conditions auto-fallback to existing block behavior.
   - Rationale: safest rollout path for mixed browser environments and live sessions.
   - Alternative considered: always-on sync for Browser TTS. Rejected due to rollout risk and operator control requirements.

5. **No canonical-path mutation invariant**
   - Decision: reveal mode mutates DOM presentation only; canonical message object and persisted output remain unchanged.
   - Rationale: preserves single visible narration path contract and history integrity.

## Architecture Boundaries

- **Config layer (`model_config.py` / template wiring):** exposes default enablement and guard flags only.
- **TTS facade (`game_interface.html` TTS functions):** chooses engine and sync strategy, owns playback lifecycle hooks.
- **Queue layer (`tts_queue_manager.js`):** serializes playback requests and carries sync metadata with queue items.
- **Render layer (`addMessage` + reveal helpers):** performs presentation-only updates and cursor animation.
- **Server layer:** unchanged canonical output path; optional minimal flag plumbing only.

## Risks / Trade-offs

- [Risk: boundary-event inconsistency across browsers] -> Detect support at runtime and fallback to block rendering with normal TTS.
- [Risk: reveal desync on stop/resume] -> Define interruption contract: preserve revealed segment, clear speaking cursor state, do not corrupt message text.
- [Risk: queue-level race between autoplay and manual click] -> Keep single active TTS invariant in queue manager and ignore stale sync callbacks.
- [Risk: CSS/layout regressions] -> Scope styles to narration reveal classes only; do not alter base message layout rules.

## Migration Plan

1. Add sync strategy constants and feature toggle wiring (default OFF).
2. Implement reveal-render helper and DOM state classes for narration messages.
3. Integrate Browser `onboundary` reveal updates into playback lifecycle.
4. Thread sync metadata through queue manager with strict single-playback invariants.
5. Add fallback path tests/smoke checks and operator docs.
6. Document deferred OpenAI-estimation path as Phase 2, behind explicit future change gate.

## Rollback Strategy

- Immediate rollback: disable sync toggle (or config default) and restart web UI session.
- Code rollback: remove reveal/sync branches while keeping existing canonical block and TTS queue logic intact.
- Safety condition: no data migration required; no persisted state format changes.

## Open Questions

1. Should sync preference be persisted in `localStorage` per browser profile?
2. Should manual replay after partial stop resume from current reveal position or restart from beginning?
3. For future OpenAI sync, should timing metadata come from server header estimation or client audio-duration sampling only?

## Verification Strategy

- Compile checks (if Python files touched):
  - `python3 -m py_compile model_config.py web/web_interface.py`
- Frontend sanity checks:
  - Browser TTS with sync ON: text reveal tracks speech boundaries.
  - Browser TTS with sync OFF: current block behavior unchanged.
  - OpenAI TTS path: unchanged block behavior.
  - Stop mid-playback: cursor clears, revealed text remains consistent.
- Regression guard:
  - No server narration stream events required.
  - Canonical block appears exactly once per narration message.
