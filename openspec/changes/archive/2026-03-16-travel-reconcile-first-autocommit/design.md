## Context

Travel is currently the clearest immersive-play failure domain. The narrator may describe movement naturally, but if the assistant omits or mis-shapes `transitionLocation`, the runtime and validator stack can reject the turn or allow narration/state drift. Upstream MoonlightByte tolerated more narrator breathing room, but it still relied too heavily on perfect manual action emission. The current gametest build swung too far toward reject-first policing.

This change follows the intended direction established in `plans/archive/llm-wants-to-be-free.md`: not an upstream rollback, and not a deterministic script engine. The target is narrator-loose, reconcile-first, mechanically strict travel handling.

This slice is expected to build on the narrow authoritative packet foundation from `narrative-sovereignty-state-packet-foundation`. If that foundation is not yet implemented, this design SHOULD still preserve a clean handoff so travel reconciliation can consume packet truth as soon as it exists.

Constraints:
- Preserve hard topology legality.
- Preserve current JSON/action schema compatibility.
- Preserve explicit `transitionLocation` flow.
- Keep the slice focused on travel only.
- Avoid broad prompt/validator rewrites unless parity is necessary.
- Keep all host-file integration additive and marked with `# TABLETOP MODE:` comments.

## Goals / Non-Goals

**Goals:**
- Auto-commit legal narrated travel when destination is resolvable and topology-safe.
- Persist an in-transit/progress state when travel is clear but exact arrival is not yet committed.
- Reduce travel retry loops caused only by missing explicit travel actions.
- Preserve hard failure for impossible or unsafe movement.
- Keep explicit `transitionLocation` as a preferred supported path.

**Non-Goals:**
- No NPC scene-presence reconciliation in this change.
- No global validator redesign.
- No prompt-stack philosophical reset beyond local parity updates.
- No event ledger or Titans runtime work.
- No combat architecture changes.

## Decisions

### Decision 1: Travel reconcile-first activates only on classified travel-intent turns

The runtime SHALL only enter reconcile-first travel logic when the existing travel-intent classifier marks the turn as movement intent.

Rationale:
- Keeps ordinary scene description and non-travel turns out of scope.
- Reuses existing intent classification instead of expanding prose parsing to every turn.

Alternative considered:
- Inspect every narration for movement clues.
- Rejected as too broad and likely to create false commits.

### Decision 2: Explicit `transitionLocation` remains authoritative when present

When the assistant provides a valid explicit `transitionLocation`, runtime SHALL continue to treat it as the primary travel commitment path.

Rationale:
- Preserves current protocol compatibility.
- Keeps reconcile-first logic additive rather than protocol-replacing.

Alternative considered:
- Normalize all travel through inference even when explicit action exists.
- Rejected because it adds unnecessary ambiguity and risk.

### Decision 3: Narrated travel without explicit transition may commit either arrival or in-transit progress

When travel intent is clear and topology is legal:
- explicit arrival narration SHALL commit the destination,
- travel-progress narration without exact arrival SHALL commit in-transit/progress state instead of forcing fake precision or failing the turn.

Rationale:
- Matches the product rule chosen for the plan.
- Prevents current all-or-nothing failure behavior.
- Avoids pretending the runtime knows an exact node when narration does not justify one.

Alternative considered:
- Require exact node inference or reject.
- Rejected because it preserves the current brittle UX failure.

### Decision 4: Ambiguity should clarify or fail soft, not hard-loop

If travel narration is not safely resolvable to one destination or one progress interpretation, runtime SHOULD preserve current safe state and request clarification or fail open to the narrower existing path rather than entering repeated validation loops.

Rationale:
- Wrong canon commit is worse than delayed commit.
- The user specifically chose in-transit/progress state to avoid fake precision.

Alternative considered:
- Aggressive inference from soft prose.
- Rejected as too risky for pre-tester stabilization.

### Decision 5: Time sync follows effective travel state commitment, not only explicit actions

Travel-time accounting SHALL attach to the effective committed travel state whether travel was committed through explicit action or runtime reconciliation.

Rationale:
- Time passage is part of travel truth.
- Current spec already supports deterministic auto-time once a transition exists; this change extends that principle to inferred commits.

Alternative considered:
- Keep time-sync restricted to explicit `transitionLocation` only.
- Rejected because it would reintroduce drift between location progress and clock progress.

## Risks / Trade-offs

- [Risk] Inferred arrival could commit the wrong destination.
  -> Mitigation: require clear resolvable destination cues for arrival commit; otherwise commit only progress or request clarification.

- [Risk] In-transit state could become vague or underused.
  -> Mitigation: keep the state narrowly defined for gametest and tie it to known destination/progress cues only.

- [Risk] Existing transition guard logic could conflict with new reconciliation behavior.
  -> Mitigation: preserve explicit `transitionLocation` precedence and narrow reconcile-first logic to missing/insufficient explicit travel state only.

- [Risk] This slice could sprawl into validator or NPC systems.
  -> Mitigation: keep NPC presence and broader validator refactors out of scope unless required for local travel correctness.

## Migration Plan

1. Lock contract behavior with travel transcript tests first.
2. Implement or consume authoritative packet truth for travel inputs.
3. Add reconcile-first travel inference for explicit arrival and in-transit progress.
4. Extend effective travel-time sync to inferred commits.
5. Narrow travel-domain validation to prefer reconciliation over rejection where legal.
6. Add prompt/validator parity wording only if runtime regressions show mismatch.

Rollback strategy:
- Revert inferred in-transit behavior first if it causes instability.
- Preserve explicit-arrival auto-commit if it proves stable and valuable.
- Keep the tests and OpenSpec contract even if a narrower travel reconcile subset must ship first.

## Open Questions

- Whether the initial in-transit/progress state should live only in `party_tracker.json` world conditions or also in a more structured helper-owned representation.
- Whether reconcile-first travel should auto-normalize missing `updateTime` into a synthetic action object or apply time purely as runtime side effect for inferred commits.
- Whether small prompt/validator parity text is needed for the gametest build, or whether runtime-only changes are sufficient.
