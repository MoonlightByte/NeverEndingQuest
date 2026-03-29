## Context

`updateCharacterInfo` now supports additive structured `ops`, but runtime recovery is asymmetric. Invalid or unsupported ops can degrade at classification time, while syntactically valid ops that fail during deterministic apply still hard-fail the turn even when prose `changes` exists as a safe fallback. The recent Redax Divine Sense failure exposed the most visible variant of this problem: prompt-facing feature labels were compacted to `DivineSense`, while runtime matching still expected the persisted feature name `Divine Sense`.

This change is cross-cutting because the failure path spans multiple runtime layers: payload classification, deterministic apply, action orchestration, and user-facing error surfacing. The design therefore MUST preserve Python mechanical authority for true contradictions while allowing recoverable target-label and shape drift to degrade safely.

## Goals / Non-Goals

**Goals:**
- MUST introduce canonical target normalization for deterministic character ops targets before apply-time rejection.
- MUST distinguish recoverable deterministic apply failures from authoritative invalid-state contradictions.
- MUST make mixed `changes + ops` payloads fail open for recoverable apply-time errors when prose fallback exists.
- MUST preserve fail-closed behavior for true mechanical contradictions and unsupported no-fallback cases.
- MUST improve observability and user-safe feedback so runtime does not collapse into opaque generic character update failure messages.
- SHOULD generalize beyond class features to other current or near-term structured-op targets such as inventory, ammunition, and slot labels.

**Non-Goals:**
- MUST NOT silently accept mechanically impossible updates.
- MUST NOT remove or weaken deterministic ops as the primary runtime path for supported operations.
- MUST NOT change 5e mechanics semantics, class resource limits, or inventory ownership rules.
- SHOULD NOT depend on tabletop-only mode gates; the recovery model should remain safe for single-player mode as well.

## Decisions

### Decision: Introduce canonical target identity matching for deterministic ops
- MUST add a shared normalization step that converts target labels into a stable canonical identity before deterministic matching.
- MUST normalize at least case, spaces, punctuation, apostrophes, hyphens, and compacted/camel-like variants.
- MUST prefer exact persisted-name matches first, canonical identity matches second, and looser contains-style matching last.
- SHOULD centralize this logic in a helper instead of duplicating bespoke normalization in each finder.

Rationale:
- The current bug is caused by contract drift between prompt compression and runtime state naming.
- A shared canonical identity matcher fixes the immediate `DivineSense` issue and reduces future random hard fails for other compacted or formatted labels.

Alternatives considered:
- Narrow one-off alias mapping for Divine Sense only -> rejected because it would not scale and would guarantee more random user-facing failures later.
- Change the compressor only -> rejected as insufficient because other runtime target-label drift sources remain possible.

### Decision: Classify deterministic apply failures into recoverable and authoritative classes
- MUST treat target-alias mismatches, minor shape drift, and mixed-payload numeric/label formatting issues as recoverable when prose fallback is present.
- MUST treat underflow, overflow, impossible removals, and other authoritative contradictions as hard failures.
- MUST preserve a structured internal reason code for each class so tests and diagnostics can lock behavior.

Rationale:
- UX improves only if runtime can distinguish a safe degrade case from a real state-integrity violation.
- This keeps Python as the truth source while avoiding avoidable turn freezes.

Alternatives considered:
- Fail open for all mixed-payload apply-time errors -> rejected because it could mask true mechanical contradictions.
- Keep current fail-closed behavior everywhere -> rejected because it creates brittle user-facing freezes for benign alias drift.

### Decision: Mixed payloads with prose fallback degrade at apply time, not just classification time
- MUST allow mixed `changes + ops` payloads to fall back to prose when deterministic apply fails for a recoverable reason.
- MUST keep structured-only payloads fail closed when no prose fallback exists.
- SHOULD reuse the existing routing-marker telemetry pattern rather than inventing a separate side channel.

Rationale:
- The system already accepts prose fallback at classification time; apply-time recovery should honor the same UX principle.
- This is the narrowest behavior change that fixes the freeze without discarding deterministic ops.

### Decision: Improve user-safe error surfacing while keeping debug detail available
- MUST stop surfacing opaque generic character-update failures for recoverable cases.
- MUST provide concise user-safe failure text for authoritative blocked updates.
- SHOULD log detailed structured diagnostics separately for debugging and regression verification.

Rationale:
- A facilitator-facing game freeze with no explanation is a worse UX failure than a safely degraded turn.
- Keeping detailed logs still supports bug diagnosis without leaking implementation noise into normal play.

### Decision: Keep the rollout helper- and test-driven
- SHOULD implement normalization and classification in helpers near `update_character_info` rather than spreading policy across unrelated modules.
- MUST add regression coverage before widening fallback behavior.
- SHOULD update prompt/runtime contract tests only where spec-visible behavior changes.

Rationale:
- This remains merge-safe and easier to reason about than broad architectural churn.

## Risks / Trade-offs

- [Recoverable classification is too broad and masks true contradictions] -> Mitigation: lock the recoverable-vs-authoritative split in spec text and regression tests; keep underflow/overflow/impossible-removal as hard-fail invariants.
- [Canonical matching picks the wrong target when names are similar] -> Mitigation: exact match first, canonical identity second, loose match last; ambiguous results MUST remain fail closed.
- [Silent degrade hides that ops generation quality is slipping] -> Mitigation: preserve routing markers and diagnostics for every fallback path; treat recovery as observable degraded behavior, not invisible success.
- [User-facing errors remain confusing] -> Mitigation: add explicit authoritative failure text and avoid bubbling raw generic exception wrappers into chat.
- [SP/MP behavior diverges] -> Mitigation: keep recovery logic mode-agnostic and test it through generic `updateCharacterInfo` paths.

## Migration Plan

1. Add canonical target identity helpers and wire them into feature/item/ammo finders.
2. Add deterministic apply failure classification and recoverable fallback routing for mixed payloads.
3. Improve action-handler/main-path error surfacing so authoritative failures remain specific and recoverable failures do not freeze the turn.
4. Add regression coverage for alias normalization, mixed apply-time fallback, and preserved hard-fail contradictions.
5. Validate the OpenSpec change and implementation-ready task set before coding.

Rollback strategy:
- Revert apply-time fallback routing while keeping non-invasive normalization helpers if needed.
- If a regression shows contradictions being masked, restore hard-fail behavior for the affected op class and keep the new diagnostics for investigation.

## Open Questions

- Should recoverable fallback emit a user-visible degraded notice in rare cases, or stay silent unless no safe outcome can be produced?
- Should spell-slot and condition target aliases be normalized in the same helper immediately, or staged after feature/item/ammo coverage proves stable?
- Should the character sheet compressor be adjusted later to reduce label drift at the source, or is runtime canonicalization sufficient as the primary contract?