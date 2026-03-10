## Context

The existing deterministic mechanics precheck already blocks a small set of explicit contradictions before the LLM validator runs. That layer has proven useful because it reduces retry churn and keeps Python-ground-truth mechanics from depending entirely on probabilistic interpretation. The next step is to expand the same pattern carefully, not broadly.

This change adds a few more deterministic guard domains that are both high-value and reasonably parseable from existing narrator-style mechanics text. The main constraint is still false-positive control: if the text is not explicit, the precheck must defer to the existing validation flow.

## Goals / Non-Goals

**Goals:**
- Extend deterministic precheck coverage to explicit spell-slot, unconscious/HP, ammo, and rest-duration contradictions.
- Preserve the current fail-open philosophy for ambiguous prose.
- Keep implementation helper-driven and small.
- Lock source contracts and negative tests before broader runtime tightening.

**Non-Goals:**
- No broad NLP interpretation layer.
- No dice-engine work.
- No combat-flow rewrite.
- No global validator-routing redesign.
- No mandatory prompt rewrites unless a later step needs narrow wording alignment.

## Decisions

### Decision 1: Extend the existing precheck utility instead of creating a second validator path

**Decision:** The expanded guards SHALL build on the current deterministic precheck path rather than introducing a separate parallel gate.

**Rationale:** The repo already has a bounded precheck boundary and tests around it. Extending that path keeps the mental model simple.

### Decision 2: Spell-slot legality remains explicit-text only

**Decision:** The spell-slot guard SHALL only reject contradictions when the narrator text explicitly indicates a cantrip consuming a slot or a leveled spell spend that would underflow known slots.

**Rationale:** We want high-value catches without broad semantic inference.

### Decision 3: Unconscious-vs-HP guard applies only to explicit mechanical claims

**Decision:** The HP/state guard SHALL reject only explicit mechanical contradictions such as text that simultaneously claims `HP 5` (or equivalent above-zero total) and `unconscious` or equivalent incapacitated-at-zero-only state.

**Rationale:** Narrative descriptions like "reeling" or "barely conscious" must remain valid flavor.

### Decision 4: Ammo legality should go beyond plain "Removed N arrows"

**Decision:** The ammo guard SHALL cover explicit fire/spend/use language for tracked ammunition, not only simple remove-from-inventory wording.

**Rationale:** Ammo legality is a common drift area and should be checked where deterministic item matching is still reliable.

### Decision 5: Rest-duration legality belongs in deterministic precheck when duration is parseable

**Decision:** The precheck SHALL reject explicit rest requests that violate minimum duration requirements when the duration can be parsed deterministically.

**Rationale:** This is a clean rules boundary and avoids needless validator retries on obvious contradictions.

### Decision 6: Ambiguity still fails open

**Decision:** If duration, slot state, ammo match, or HP/state claims are ambiguous or not parseable, the deterministic guard SHALL pass and defer to existing validation.

**Rationale:** False positives would damage player trust more than a small number of misses.

## Guard Domains

### A. Spell-slot legality
- Cantrip text that explicitly consumes a slot -> deterministic failure.
- Explicit slot spend that would underflow known slots -> deterministic failure.
- Unknown or implied slot language -> fail open.

### B. Unconscious vs HP integrity
- Explicit HP target above 0 plus explicit unconscious condition -> deterministic failure.
- Flavor text without explicit mechanical contradiction -> fail open.

### C. Ammo legality
- Explicit ammunition spend/use/fire language with insufficient known ammo -> deterministic failure.
- Unknown ammo type or unmatched inventory item -> fail open.

### D. Rest duration legality
- Explicit short rest under 60 minutes -> deterministic failure.
- Explicit long rest under 8 hours -> deterministic failure.
- Natural-language duration that cannot be parsed confidently -> fail open.

## Risks and Mitigations

- **Risk:** Over-matching flavor words as mechanics.
  - **Mitigation:** Require explicit numeric/mechanical patterns and narrow keyword scopes.
- **Risk:** Ammo matching ambiguity.
  - **Mitigation:** Enforce only when deterministic tracked-ammo match succeeds.
- **Risk:** Rest parsing becomes too broad.
  - **Mitigation:** Limit to clearly parseable explicit durations in this change.
- **Risk:** Slot legality creates false positives on unusual class features.
  - **Mitigation:** Restrict this phase to explicit cantrip-slot contradictions and known underflow checks only.

## Migration Plan

### Phase 1 - Contract and tests
- Add focused source-contract tests for the expanded guard set.
- No runtime changes yet.

### Phase 2 - Helper expansion
- Extend deterministic precheck helper functions for the new guard domains.
- Keep helpers small and explicit-pattern driven.

### Phase 3 - Pipeline wiring and narrow prompt parity
- Ensure main validation path uses the new helpers.
- Add prompt/validator wording only if required to prevent contract drift.

### Phase 4 - Negative-path and fail-open verification
- Add false-positive resistance tests and ambiguous-text pass cases.

### Phase 5 - Final verification
- Run targeted suites, syntax checks, and `openspec validate`.

## Deferred Follow-Ups

- Richer spell legality involving class-specific exceptions.
- Stronger unconscious/stable/death-save cross-checking.
- Broader natural-language rest parsing.
- Prompt-level tightening once telemetry confirms low false-positive rates.
