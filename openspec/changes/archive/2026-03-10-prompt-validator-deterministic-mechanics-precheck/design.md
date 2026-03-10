## Context

The narrator pipeline already has deterministic pre-validation for NPC arrival sync. Mechanics contradictions in `updateCharacterInfo` are still mostly mediated by the LLM validator, which is helpful but probabilistic. This change introduces a deterministic mechanics gate for a narrow set of explicit contradictions.

## Goals / Non-Goals

**Goals:**
- Add deterministic precheck for explicit mechanics contradictions in `updateCharacterInfo` changes.
- Keep checks bounded and parseable so false positives remain low.
- Fail closed when contradiction is explicit and deterministic.
- Fail open when text is ambiguous or not parseable.

**Non-Goals:**
- No broad NLP interpretation layer.
- No rewrite of `update_character_info` processing.
- No schema generator for change strings.
- No combat/save/module contract work in this change.

## Decisions

### Decision 1: Precheck only explicit parseable patterns

**Decision:** The deterministic gate SHALL only act when explicit numeric patterns are detected.

**Rationale:** `changes` is freeform text; broad interpretation would cause false positives and over-block valid narration.

### Decision 2: Keep runtime state as baseline

**Decision:** Character state loaded from canonical character files SHALL be the truth source for max HP and known item quantities.

**Rationale:** This follows existing Python-ground-truth architecture.

### Decision 3: Integration point is before LLM validator call

**Decision:** Deterministic mechanics precheck SHALL run in `validate_ai_response()` after JSON normalization and before LLM validation request.

**Rationale:** Hard contradictions should be blocked early to reduce retry churn and API spend.

### Decision 4: Limited contradiction classes in this phase

**Decision:** Phase scope is limited to:
- HP target outside valid range when explicit totals are present
- Spell-slot `current/max` ratio contradictions when explicit
- Item-removal quantity greater than known tracked amount when explicit and matched

**Rationale:** High-value checks with low parsing ambiguity.

## Risks and Mitigations

- **Risk:** False positives from freeform text parsing.
  - **Mitigation:** Only enforce on explicit numeric patterns; otherwise pass.
- **Risk:** Item-name matching ambiguity.
  - **Mitigation:** Enforce only when deterministic match to tracked item is found.
- **Risk:** Runtime overhead.
  - **Mitigation:** Scope checks only to `updateCharacterInfo` actions and parseable patterns.

## Migration Plan

1. Add deterministic precheck utility with isolated helper functions.
2. Add tests for helper behavior (pass/fail/fail-open).
3. Wire utility into `validate_ai_response()`.
4. Add integration/source-contract test for pipeline call point.
5. Run targeted verification and archive.

## Deferred Follow-Ups

- Expand deterministic checks to additional mechanics only after telemetry confirms low false-positive rate.
- Consider richer structured update contracts in future phases.
