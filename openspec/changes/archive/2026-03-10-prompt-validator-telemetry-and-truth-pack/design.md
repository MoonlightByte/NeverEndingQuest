## Context

The validation pipeline now has better guardrails, but it is still difficult to tune because routing outcomes are not surfaced cleanly. It also still assembles character validation context in an uneven way, favoring inventory dumps over a compact mechanics-first truth view.

This change adds observability and a compact touched-character truth pack. It is intentionally a measurement-and-clarity slice, not a broader rewrite.

## Goals / Non-Goals

**Goals:**
- Add deterministic telemetry for validation skip and compression decisions.
- Build a compact mechanical truth pack for touched characters.
- Integrate that truth pack into validation context assembly.
- Preserve existing conservative validation behavior.

**Non-Goals:**
- No expansion of skip eligibility in this change.
- No structured ops support.
- No save/check contract changes.
- No combat-specific prompt refactor.

## Decisions

### Decision 1: Telemetry must be deterministic and cheap

**Decision:** Routing telemetry SHALL be recorded as lightweight reason-coded metadata rather than heavy tracing.

**Required fields:**
- `skip_llm_validation`
- `skip_reason`
- `used_validation_compression`
- `compression_reason`
- `validation_payload_chars`

**Rationale:** These are enough to tune thresholds and identify misrouting without introducing heavy overhead.

### Decision 2: Truth pack is touched-character scoped

**Decision:** Validation truth packs SHALL be built only for characters referenced by `updateCharacterInfo` in the candidate response.

**Rationale:** This keeps token weight low and focuses validation on relevant mechanics.

### Decision 3: Mechanics-first fields are mandatory

**Decision:** Each touched-character truth pack SHALL prioritize live mechanics over prose summaries.

**Required fields:**
- character name
- current HP / max HP
- active conditions
- spell slot summary
- death save summary
- class feature usage summary when present
- relevant inventory summary only when the current change text references inventory/currency/ammunition/equipment

### Decision 4: Inventory remains conditional

**Decision:** Inventory SHALL be included in the truth pack only when the touched update appears inventory-relevant.

**Rationale:** This reduces validator prompt size on HP/slot-only turns.

### Decision 5: Keep the integration additive

**Decision:** This change SHALL wrap and replace the current touched-character context assembly gradually rather than rewriting unrelated validation context blocks.

**Rationale:** Lower risk and easier verification.

## Risks and Mitigations

- **Risk:** Telemetry fields could drift if logged ad hoc in many places.
  - **Mitigation:** Centralize routing helper return shapes and pack assembly helper output.
- **Risk:** Truth-pack field extraction could become too verbose.
  - **Mitigation:** Keep summaries compact and touched-character-only.
- **Risk:** Inventory relevance heuristic may miss edge cases.
  - **Mitigation:** Start with a conservative keyword-based heuristic and fail open by including inventory when uncertain.

## Migration Plan

### Phase 1 - Tests and helper contracts
- Add tests for telemetry helper return shape and truth-pack content.
- Add source-contract test for `main.py` wiring.

### Phase 2 - Routing telemetry helper
- Extend validation routing helper(s) to return reason-coded telemetry.
- Integrate telemetry fields into validation path debug/export payloads.

### Phase 3 - Mechanical truth-pack helper
- Add helper to build touched-character truth packs from canonical character files.
- Add conditional inventory inclusion.

### Phase 4 - Validation context integration
- Replace current touched-character inventory-heavy context with truth-pack output.
- Preserve fallback behavior if helper fails.

## Deferred Follow-Ups

- Telemetry-driven threshold tuning.
- Broader low-risk skip eligibility.
- Structured mechanics ops.
- Shared truth-pack use for both validator and narrator if beneficial.
