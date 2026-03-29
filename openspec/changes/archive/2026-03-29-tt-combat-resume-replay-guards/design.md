## Context

Resumed combat currently differs from the normal combat-complete handoff in two important ways. First, resumed turns can process stale combat actions against encounter state that already reflects the same HP change, which makes supported enemy ops non-idempotent under crash recovery. Second, the resumed-session path appends a plain `[COMBAT CONCLUDED]` summary to main history instead of the normal historical-record wrapper, so the main loop can reinterpret the summary as a fresh actionable turn and duplicate XP/reward updates.

## Goals / Non-Goals

**Goals:**
- MUST prevent already-applied resumed enemy HP results from being applied a second time.
- MUST keep authoritative encounter state as the source of truth for whether a resumed enemy result is already committed.
- MUST reuse the historical-record post-combat summary contract in resumed sessions so XP and combat state are not replayed.
- SHOULD keep the fix narrow and additive to resume paths and deterministic encounter update handling.

**Non-Goals:**
- MUST NOT redesign general combat prompting, validation, or reward calculation.
- MUST NOT change non-resume combat behavior except where shared historical-summary handling is intentionally unified.
- MUST NOT introduce new persistent combat ledgers if a narrower idempotency guard is sufficient.

## Decisions

### Decision: Use authoritative-state idempotency checks for resumed enemy result replay
- MUST detect replay only when runtime can prove that the encounter already matches the intended post-update enemy state.
- MUST prefer a no-op over reapplying enemy damage when the prose mirror indicates the final HP/status is already committed.
- SHOULD implement the guard in deterministic encounter update handling so both combat-manager immediate updates and resumed paths benefit from the same protection.
- Alternative considered: storing a durable processed-action ledger. Rejected for this bugfix because it is broader, riskier, and unnecessary for the observed replay class.

### Decision: Unify resumed combat summary handoff with historical-record wrapper
- MUST append resumed combat summaries with the same historical marker and explicit no-reward replay note used by the normal combat completion path.
- SHOULD centralize or closely mirror the existing normal-path wrapper to reduce divergence between resumed and non-resumed combat exits.
- Alternative considered: teaching action prediction to special-case plain `[COMBAT CONCLUDED]` text. Rejected because it leaves duplicate semantics in history and does not enforce a single canonical historical-summary contract.

### Decision: Preserve fail-open behavior when replay cannot be proven
- MUST only suppress replay when the current encounter state already equals the summarized final enemy state.
- SHOULD keep normal application behavior for ambiguous updates so legitimate damage is not lost.

## Risks / Trade-offs

- [False positive replay suppression] -> Mitigation: require current authoritative HP/status to already match the summarized final state before suppressing apply.
- [Resume/non-resume path drift returning later] -> Mitigation: reuse the same historical-record summary wrapper semantics in both paths.
- [Narrow prose parsing brittleness] -> Mitigation: keep parsing limited to the existing `HP old->new` mirror pattern used by combat actions and cover it with regressions.

## Migration Plan

1. Add OpenSpec regression coverage for resumed duplicate enemy-damage replay and resumed combat-summary XP replay.
2. Implement historical-summary unification for resumed combat handoff.
3. Add deterministic replay no-op guard around resumed enemy HP/state updates.
4. Verify with targeted combat regression scripts and smoke the resumed-combat flow.
5. Rollback strategy: remove the resume-specific guardrails and restore previous resume path behavior if any legitimate combat mutations are suppressed unexpectedly.

## Open Questions

- None for this compact bugfix if the current `HP old->new` combat prose mirror remains available in resumed encounter updates.
