## Context

Combat validation already has a modernized authority chain, truth-pack support, structured PC/allied updates, and explicit request-roll pause contracts. The remaining high-value gap is not more narration structure; it is deterministic rejection of explicit contradiction classes that still leak into probabilistic validation.

This change applies the repo's deterministic-first philosophy to a narrow combat-only set of contradiction classes. The key constraint remains false-positive resistance: if combat text is ambiguous, the deterministic layer must defer to existing validation instead of inventing certainty.

## Goals / Non-Goals

**Goals:**
- Add bounded deterministic guards for explicit combat mechanics contradictions.
- Add bounded deterministic guards for explicit combat phase-integrity contradictions.
- Preserve fail-open behavior for ambiguous combat text.
- Keep implementation additive and small.
- Lock the contract in tests before helper/runtime tightening.

**Non-Goals:**
- No `updateEncounter.ops` work.
- No roll resolution engine.
- No broad prompt rewrite.
- No style/tactics validation.
- No non-combat narrator guard expansion.

## Decisions

### Decision 1: Guard only explicit contradiction classes

**Decision:** Combat deterministic guards SHALL reject only contradiction classes that are explicit in text and checkable against authoritative combat/runtime state.

**Rationale:** The goal is lower hallucination surface without converting combat validation into broad NLP interpretation.

### Decision 2: Mechanical contradiction guards remain bounded to state-backed claims

**Decision:** The mechanics guard set SHALL cover only these explicit domains in this change:
- unconscious vs HP contradictions
- ammo underflow for explicit ranged-ammo spend/use
- spell-slot underflow for explicit combat casting/spend language

**Rationale:** These are high-value, parseable, and state-backed. They improve legality without widening into ambiguous judgment.

### Decision 3: Phase-integrity guards remain bounded to authoritative turn/phase state

**Decision:** The phase guard set SHALL cover only these explicit domains in this change:
- illegal action by forbidden phase actor
- illegal stop mid enemy batch
- illegal exit while hostiles remain
- illegal round increment before all PCs acted

**Rationale:** These contradictions already have authoritative state in the combat runtime and fit the deterministic-first model.

### Decision 4: Ambiguity fails open

**Decision:** If a contradiction cannot be confirmed from authoritative combat/runtime state plus explicit text, the deterministic guard SHALL pass and defer to existing validation.

**Rationale:** False positives would damage trust more than a small number of misses.

### Decision 5: Prompt/validator wording is parity work, not the main implementation target

**Decision:** Prompt and validator edits SHALL occur only if helper/runtime implementation reveals source-contract drift for the new guard domains.

**Rationale:** This change is primarily about deterministic enforcement, not prompt expansion.

## Guard Domains

### A. HP / unconscious contradictions
- Explicit above-zero HP plus explicit unconscious-only mechanical state -> deterministic failure.
- Flavor text like dazed, reeling, or barely standing -> fail open.

### B. Ammo underflow
- Explicit ranged attack or explicit ammo spend with insufficient tracked ammo -> deterministic failure.
- Unknown ammo type, missing inventory, or ambiguous spend text -> fail open.

### C. Spell-slot underflow
- Explicit leveled combat cast/spend that would underflow known slots -> deterministic failure.
- Ambiguous cast language or missing slot state -> fail open.

### D. Forbidden phase actor
- Explicit action by actor who is forbidden under current combat phase -> deterministic failure.

### E. Mid-enemy-batch stop
- Explicit stop/prompt before enemy batch is complete and before the next legal PC boundary -> deterministic failure.

### F. Illegal exit while hostiles remain
- Explicit combat exit while living hostiles remain -> deterministic failure.

### G. Illegal round increment before all PCs acted
- Explicit round advance before all required PC turns in the round are complete -> deterministic failure.

## Risks and Mitigations

- **Risk:** Over-matching flavor text as mechanics.
  - **Mitigation:** Require explicit mechanical language plus authoritative state support.
- **Risk:** Ammo or slot state ambiguity.
  - **Mitigation:** Fail open when inventory/slot state is unavailable or unclear.
- **Risk:** Phase-integrity guards duplicate existing combat logic inconsistently.
  - **Mitigation:** Reuse current authoritative combat phase/queue state rather than inventing parallel logic.
- **Risk:** Prompt drift after runtime tightening.
  - **Mitigation:** Add narrow parity wording only if tests reveal contract mismatch.

## Migration Plan

### Phase 1 - Contract locks and tests
- Add focused combat guard contract tests for the contradiction classes and fail-open boundaries.
- No runtime changes yet.

### Phase 2 - Helper/runtime tightening
- Extend or add narrow deterministic combat guard helpers for the explicit domains.
- Keep helpers small and state-backed.

### Phase 3 - Pipeline wiring and parity
- Ensure existing combat validation path calls the new guards.
- Add prompt/validator wording only if needed for contract parity.

### Phase 4 - Negative-path and verification
- Add ambiguous-text pass cases and explicit deterministic fail cases.
- Run targeted contracts plus combat regressions.

## Rollback Strategy

- Revert the narrow deterministic helper/wiring changes first.
- Preserve prompt/validator parity edits only if still accurate after rollback.
- Keep fail-open behavior as the default if any guard domain proves too brittle.
