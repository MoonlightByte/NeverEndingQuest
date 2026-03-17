## Context

The world clock currently advances when the model emits `updateTime` or when transition fallback injects it. That keeps action-driven travel mostly coherent, but it leaves two visible UX gaps:

1. The web runtime keeps looping during idle waits because `WebInput.readline()` eventually returns a blank line instead of blocking.
2. Real player deliberation time is invisible to the world clock, so multiple minutes of table discussion can still leave the game at the same "early morning" timestamp.

This change intentionally adopts the conservative `turn-sync only` model: time advances when a real, non-empty turn is accepted, not continuously in the background.

Constraint layer (MUST):
- Runtime MUST block on real web input and SHALL NOT synthesize blank turns during idle waits.
- World time MUST advance only from accepted non-empty player turns in this slice.
- Explicit `updateTime` actions MUST remain authoritative and unchanged.
- Turn-synced wall-clock advancement MUST be bounded per turn.
- Missing or malformed timestamp metadata MUST fail open by resetting the marker rather than blocking play.
- Inferred narrated-arrival commits MUST keep time synchronized with the committed location state.
- Host-file edits MUST remain additive, minimal, and marked with `# TABLETOP MODE:` comments.
- Python-visible strings MUST remain ASCII-only.

Guidance layer (SHOULD):
- Keep wall-clock math in one helper module rather than distributing it across `main.py`.
- Store the wall-clock marker near `worldConditions` so the persistence model stays easy to inspect.
- Use whole-minute granularity to keep behavior predictable.
- Add focused regression tests instead of broad integration rewrites.

## Goals / Non-Goals

**Goals:**
- Stop idle blank-turn churn in the web runtime.
- Advance world time by bounded elapsed real minutes on each accepted turn.
- Preserve existing explicit action-driven time semantics.
- Synchronize narrated-arrival reconcile-first commits with deterministic time advancement.
- Add regression coverage for blocking behavior, wall-clock clamping, and inferred-arrival time parity.

**Non-Goals:**
- Continuous live clock ticking while players think.
- Background UI polling that mutates the clock with no player turn.
- A new settings toggle or hybrid mode in this slice.
- Replacing the current `updateTime` contract for rests, travel, or combat.

## Decisions

### Decision: web input MUST block until real input arrives
- `WebInput.readline()` SHALL wait for queued user input instead of returning synthetic newline values after timeout.
- The runtime SHALL continue to support status/heartbeat signaling without feeding fake turns into `main.py`.
- Rationale: the current timeout fallback is the direct source of idle loop churn and repeated housekeeping.

### Decision: turn-synced wall-clock advancement is anchored to accepted non-empty turns
- Runtime SHALL compute elapsed real minutes only when the main loop accepts a non-empty player input.
- The first accepted turn after marker creation SHALL initialize the wall-clock marker and SHALL NOT advance world time.
- Subsequent accepted turns SHALL advance world time by elapsed whole minutes since the prior accepted turn.
- Rationale: this keeps the model simple, deterministic, and reviewable while still making table discussion visible in the game clock.

### Decision: bounded per-turn clamp prevents runaway AFK time skips
- Runtime SHALL clamp wall-clock advancement to a fixed per-turn maximum.
- The initial slice SHALL use a conservative bound suitable for table discussion windows rather than long absences.
- The clamp MUST be deterministic and centralized in helper logic.
- Rationale: without a clamp, a paused tab or lunch break could fast-forward the campaign unrealistically.

### Decision: timestamp persistence is additive and fail-open
- Runtime SHALL persist a wall-clock marker in `party_tracker.json` as additive metadata.
- If the stored marker is missing, malformed, or unparseable, runtime SHALL reset it and skip time advancement for that turn.
- Runtime SHALL continue gameplay normally after the reset.
- Rationale: the helper must be robust across reloads, edits, and older save states.

### Decision: narrated-arrival reconcile-first commits MUST carry deterministic time sync
- When runtime infers a safe narrated arrival commit without an explicit `updateTime`, it SHALL also infer deterministic time advancement in the same effective commit cycle.
- Deterministic minutes SHALL follow the same same-area/cross-area fallback semantics already used for explicit travel fallback unless explicit time is already present.
- Rationale: location and time should not drift apart just because the location commit was inferred instead of explicitly emitted.

### Decision: explicit `updateTime` remains authoritative
- If a turn already includes explicit `updateTime`, this change SHALL NOT add another time update for the same committed travel event.
- Turn-synced wall-clock advancement SHALL remain a separate per-turn mechanism and MUST avoid duplicating explicit travel-time fallback within the same narrow inferred-arrival path.
- Rationale: explicit action bundles still define the canonical travel-time contract.

## Risks / Trade-offs

- Blocking input too aggressively could make the web loop appear frozen if queue signaling is wrong -> Mitigation: keep the change scoped to newline synthesis removal and cover it with a focused source/behavior test.
- Turn-sync plus explicit travel time could feel too fast on some turns -> Mitigation: keep the new mechanism bounded, turn-only, and avoid injecting duplicate travel-time actions when explicit time is already present.
- Stored timestamp drift across restarts could create unexpected jumps -> Mitigation: first accepted turn after reset only seeds the marker, no time advance.
- Inferred narrated-arrival time injection could duplicate existing travel fallback -> Mitigation: preserve explicit `updateTime` precedence and test the inferred-arrival path specifically.

## Migration Plan

1. Add/extend spec deltas and regression locks for idle blocking, wall-clock sync, and transition-time parity.
2. Harden `WebInput.readline()` so idle waits block instead of generating blank turns.
3. Add a narrow helper for timestamp parsing, clamp logic, party-tracker persistence, and turn-time application.
4. Call the helper from the main loop after a real non-empty user turn is accepted.
5. Extend narrated-arrival reconcile-first time inference so location commits and time commits remain paired.
6. Run targeted compile/test verification and validate the OpenSpec change.

## Open Questions

- None for the turn-sync-only slice. A future hybrid/live ticking option remains SHOULD-level follow-up work after gameplay review.
