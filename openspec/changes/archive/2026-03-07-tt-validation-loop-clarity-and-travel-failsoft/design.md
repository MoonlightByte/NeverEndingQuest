## Context

The current turn pipeline has three compounding issues:

1. Multi-PC turns receive duplicated policy text (structured DM note + appended legacy instruction tail).
2. Transition pre-validation receives an inflated "player request" containing DM note text.
3. Deterministic NPC arrival sync can repeatedly fail on travel turns, and retry feedback amplifies the same failure pattern.

## Goals

- Preserve deterministic mechanical safety.
- Reduce false-positive validation pressure during travel turns.
- Reduce retry loops and user-visible "dead turns".
- Keep changes merge-safe and additive.

## Non-Goals

- Replacing validation architecture.
- Removing NPC arrival sync.
- Relaxing combat/state integrity contracts.

## Decisions

### D1 - Multi-PC Rule Source Deduplication

- MUST: Multi-PC turn construction use one concise instruction source.
- MUST: Legacy common instruction tail not be appended to multi-PC DM note path.
- SHOULD: Single-PC path remain unchanged unless needed for bug parity.

### D2 - Raw Player Intent for Transition Validator

- MUST: `pre_validate_transition(...)` pass raw user utterance as transition `player_request`.
- MUST: Transition validator prompt no longer consume full DM note payload as player request.
- SHOULD: Keep existing atlas/path/plot context unchanged.

### D3 - Travel-Turn Fail-Soft NPC Arrival Guard

- MUST: NPC arrival sync stay fail-closed for explicit off-location arrival claims.
- MUST: On travel-intent turns, non-arrival mention phrasing not hard-fail NPC arrival sync.
- MUST: Explicit arrival semantics (arrives/joins/enters/appears from elsewhere) still require action pairing.
- SHOULD: Keep ambiguity fail-open policy and party-member exemption unchanged.

### D4 - Retry De-Looping for Deterministic Guard Failures

- MUST: Deterministic guard failures avoid appending failed assistant output back into history.
- MUST: Retry note be short, normalized, and action-focused.
- SHOULD: If same deterministic reason repeats twice in one turn, abort early with concise system guidance instead of consuming full retry budget.

## Risk and Mitigation

- Risk: Over-softening could miss real NPC arrivals.
  - Mitigation: explicit-arrival semantic gate remains strict.
- Risk: prompt behavior drift from removed legacy tail.
  - Mitigation: retain structured multi-PC DM note sections and existing system prompt rules.

## Verification Strategy

- Compile checks on modified Python files.
- Regression tests:
  - existing NPC arrival suite,
  - new travel fail-soft and explicit-arrival fail-closed tests,
  - new retry-loop behavior test(s).
- Manual smoke:
  - travel request from current location to known destination,
  - no repeated "no NPCs here" loop,
  - transition executes with valid actions.
