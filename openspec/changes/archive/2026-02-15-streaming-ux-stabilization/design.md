## Context

The dual-pipeline streaming implementation introduced draft stream events plus commit/supersede lifecycle semantics. Live gameplay exposed a mismatch between control-plane payload shape and display-plane rendering:

- Draft deltas can include JSON wrapper tokens before narration extraction.
- Final accepted narration can also be emitted through existing block output flow.
- Startup has two branches with differing stream behavior.
- Stream TTS queue can saturate when deltas arrive faster than playback.

The core architecture remains valid; this change hardens integration boundaries to restore predictable UX.

## Goals / Non-Goals

**Goals:**
- Ensure streamed draft text shown to players is narration-safe.
- Guarantee one rendered canonical narration per turn.
- Normalize startup narration behavior across branches.
- Keep stream TTS responsive and bounded under long outputs.

**Non-Goals:**
- No mechanic/state model changes.
- No changes to combat command semantics or action schema.
- No provider routing redesign.

## Decisions

### Decision 1: Enforce display-plane sanitization boundary

Choice:
- For JSON-shaped generation flows, do not surface raw provider token stream directly to player draft UI.
- Only narration-safe content may be emitted as draft deltas.

Rationale:
- Prevents braces/escape tokens from leaking into chat and TTS.

Alternative considered:
- Keep raw token stream and rely on frontend post-cleanup.
- Rejected due to unstable partial JSON and repeated leakage.

### Decision 2: Add per-turn render dedupe contract

Choice:
- Track turn-level committed render state and suppress subsequent duplicate block narration for the same accepted turn.

Rationale:
- A turn should have one canonical visible narration output.

Alternative considered:
- Keep both draft and final block visible.
- Rejected due to duplicate/confusing UX.

### Decision 3: Unify startup stream policy across branches

Choice:
- Startup path uses one deterministic policy regardless of injected-return or normal-start branch.

Rationale:
- Avoids environment-dependent behavior where startup sometimes streams and sometimes does not.

Alternative considered:
- Preserve branch-specific behavior.
- Rejected because it obscures regressions and user expectations.

### Decision 4: Bound stream TTS queue during active stream

Choice:
- Allow at most one currently speaking utterance plus a limited pending sentence budget during active stream.
- On supersede, clear stale pending fragments and stop active stale playback according to current cancellation policy.

Rationale:
- Prevents queue churn and delayed playback start on long streamed outputs.

Alternative considered:
- Unlimited sentence enqueue.
- Rejected due to queue overflow behavior observed in live sessions.

## Risks / Trade-offs

- Less granular visual streaming if sanitization gates are conservative.
  - Mitigation: preserve commit speed and fallback path.
- Dedupe false positives if turn identity is too coarse.
  - Mitigation: key by `turnId` + `streamId` attempt metadata.
- TTS cancellation could feel abrupt during retries.
  - Mitigation: keep supersede visibility/config behavior explicit.

## Validation Plan

- Unit checks:
  - No raw JSON token leakage into stream-rendered text.
  - Exactly one canonical visible narration render per successful turn.
  - Startup branch parity for stream policy.
  - Stream TTS queue remains bounded under rapid deltas.
- Integration checks:
  - SP and MP smoke runs with streaming on/off in narrative and combat contexts.
- Operational checks:
  - Confirm `status_update` remains sole lock authority.
  - Confirm `game_output` compatibility remains for fallback flows.
