## Context

The runtime already has several adjacent pieces:
- a phrase-level travel intent classifier,
- transition pre-validation for explicit `transitionLocation` actions,
- deterministic retry-local correction handling for guard failures,
- and time-sync fallback once a transition action exists.

What is missing is a commitment check between narration and state. If the model narrates travel but omits `transitionLocation`, the response can still pass structural validation because `actions` may be empty or auto-added. That lets narration describe arrival in a new place while `currentLocationId` remains unchanged.

The Night transcript shows the exact failure shape:
- narration reaches the spider/storage chamber,
- then the same response or the next one re-grounds the party in Ma's cellar,
- and the stale current-location truth wins.

## Goals / Non-Goals

**Goals:**
- deterministically reject narration-only travel on clear travel-intent turns
- allow explicit blocker/clarifier/current-location responses without forcing invalid transitions
- reject contradictory dual-location travel narration when no valid state transition explains it
- keep the guard additive and small
- preserve current transition validator, same-location stripping, and updateTime fallback behavior

**Non-Goals:**
- no transcript/history cleanup logic
- no module graph validation work
- no broad prompt rewrite or scene parser
- no forced destination inference from vague prose when the destination is ambiguous

## Decisions

### Decision 1: Use travel intent as the activation gate

The guard SHALL activate only when the existing runtime has already classified the user utterance as clear travel intent.

Rationale:
- This keeps non-travel descriptive turns, questions, and exploration chatter out of scope.
- The repository already has a travel-intent classifier contract; reuse avoids duplicate policy.

Alternative considered:
- Always inspect all responses for location narration.
- Rejected as too broad and likely to false-positive on ordinary scene description.

### Decision 2: Arrival narration without transition action is the primary deterministic failure

When a clear travel-intent response explicitly narrates arrival/entry/emergence at a new location, but no `transitionLocation` action exists, the runtime SHALL reject the response before accepting it.

Rationale:
- This is the core bug class.
- The current runtime only validates transitions if a transition action already exists, which is too late for narration-only travel drift.

Alternative considered:
- Auto-infer and inject `transitionLocation` from prose.
- Rejected because it guesses destination state from freeform text and risks unsafe movement.

### Decision 3: No-transition responses remain legal only when they keep the party grounded at the current location

The guard SHALL allow a no-transition response for travel-intent turns only if the response explicitly does one of:
- blocks movement at the current location,
- asks for clarification before moving,
- or narrates failed/aborted travel without arriving elsewhere.

Rationale:
- This preserves valid fail-soft travel behavior.
- The model must still be allowed to say "the passage is blocked here" without being forced into a fake transition.

### Decision 4: Contradictory dual-location narration is a deterministic failure when explicit

If a single travel-intent response explicitly narrates arrival in one place and then re-grounds the party in a different place without state actions explaining both, the guard SHALL reject it.

Rationale:
- The Night transcript contained this exact contradictory structure.
- This can be checked narrowly when explicit location names or clear location-identifying details are present.

Alternative considered:
- Leave contradictory narration to the LLM validator.
- Rejected because the contradiction is deterministic once the current location and response text are known.

### Decision 5: Retry handling should reuse existing deterministic retry-local behavior

Travel-state sync failures SHOULD feed the existing retry-local correction path rather than inventing a second retry mechanism.

Rationale:
- Existing deterministic failure handling already avoids history contamination.
- Reuse keeps the patch small.

## Risks / Trade-offs

- [Risk] Blocker narration could be misread as illegal no-transition travel.
  -> Mitigation: permit explicit current-location blocker/clarifier/failure language as safe no-transition cases.

- [Risk] Arrival detection could over-match atmospheric language.
  -> Mitigation: require explicit arrival semantics such as reach, emerge, enter, arrive, step into, or equivalent plus destination cues.

- [Risk] Contradictory-location detection could become brittle if it relies on rich prose interpretation.
  -> Mitigation: keep this bounded to explicit mixed-location cues and fail open on ambiguity.

- [Risk] Retry loops could still feel noisy if correction notes are verbose.
  -> Mitigation: keep correction guidance concise and destination/state focused.

## Migration Plan

1. Lock contract behavior in targeted tests first.
2. Add a narrow deterministic guard in the response validation path for travel-intent turns.
3. Reuse existing retry-local correction behavior for blocked responses.
4. Add prompt/validator parity wording only if tests show contract drift.
5. Run Night-shaped regression plus healthy blocker/clarifier regressions.

Rollback strategy:
- Revert the new travel-intent guard while leaving existing travel-intent classification and transition pre-validation intact.
- Preserve any narrow test fixtures that document the bug even if the guard implementation is temporarily removed.

## Open Questions

- Whether explicit destination matching should stay fully heuristic in runtime code or eventually be supported by a structured validator helper shared with transition pre-validation.
- Whether stale recap/history remediation should become a later follow-up change once the live acceptance bug is closed.
