# Design: tt-transition-time-failopen-sync

## Context

Current architecture intentionally keeps location transition and time advancement separate:
- `transitionLocation` updates world location/area.
- `updateTime` advances clock.

This separation is correct, but reliability suffers when model output omits `updateTime` during travel.

## Goals

1. Preserve existing action model (`transitionLocation` + `updateTime`) and prompt contracts.
2. Add deterministic runtime fail-open fallback so world time cannot freeze through repeated movement turns.
3. Keep changes surgical and merge-safe (TABLETOP MODE style).

## Non-Goals

1. No global rewrite of travel planning.
2. No automatic time advancement for non-movement turns.
3. No schema changes for action contracts.

## Decisions

### D1. Runtime Fallback Trigger

After parsing one model response's `actions` list, runtime checks:
- If at least one `transitionLocation` exists, and
- No `updateTime` action exists in that same response,

then runtime appends a synthetic `updateTime` action before executing `other_actions`.

This keeps behavior fail-open and deterministic in one turn.

### D2. Deterministic Minute Policy

Fallback minutes MUST be deterministic from transition scope:
- Same-area transition (area unchanged): `10` minutes
- Cross-area transition (area changed): `20` minutes

Implementation may detect cross-area by comparing world conditions before/after transition processing.

### D3. Logging and Auditability

When fallback is applied, runtime logs one explicit line:
- `STATE_SYNC: Auto-applied updateTime=<N> due to transitionLocation without updateTime`

This line is for diagnostics only and must remain ASCII.

### D4. Contract Reinforcement (Prompt + Validation)

Prompt/validation updates SHOULD make travel bundling explicit:
- `transitionLocation` SHOULD be paired with `updateTime` in same response.
- Validator SHOULD flag missing pair as a correction signal.

Runtime fallback remains authoritative for continuity (fail-open).

## Risks and Mitigations

1. **Risk:** Double time advancement when model already includes `updateTime`.
   - **Mitigation:** Fallback trigger only fires when no `updateTime` exists.

2. **Risk:** Over-advancing clock in edge transitions.
   - **Mitigation:** Use conservative deterministic defaults (10/20) and keep policy centralized.

3. **Risk:** Upstream drift from broad refactor.
   - **Mitigation:** Scope changes to action-processing hook + prompt text + tests.

## Rollback

Fallback can be disabled by removing the synthetic-action injection block; prompt-only guidance remains safe.
