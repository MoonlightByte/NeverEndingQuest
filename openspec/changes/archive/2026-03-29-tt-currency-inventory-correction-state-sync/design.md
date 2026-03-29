## Context

The current narrator pipeline already protects several state-sensitive turns before low-risk validation skip routing runs. `main.py` executes deterministic travel reconciliation, NPC arrival reconciliation, item-transfer recovery, and possession authority checks before `should_skip_llm_validation(...)` can finalize a turn as `narration_only`. The currency/inventory bookkeeping correction class is missing from that chain, so a response can narrate a committed correction such as "that copper is in your pouch now" with `actions: []` and still pass.

This change is cross-cutting but narrow. It touches shared narrator validation/runtime code plus prompt and validator contracts, yet it MUST preserve the existing distinction between:
- pure clarification or ruling turns, which may remain narration-only, and
- committed bookkeeping changes, which MUST emit executable character-update actions.

## Goals / Non-Goals

**Goals:**
- Add a deterministic guard that MUST reject explicit bookkeeping-correction claims when matching `updateCharacterInfo` actions are absent.
- Ensure low-risk `narration_only` skip routing MUST NOT accept explicit bookkeeping-correction turns.
- Align compressed prompt and validator contracts so ruling-only clarification remains legal, but state-changing bookkeeping narration is not.
- Keep the fix merge-safe and backward compatible for both single-player and tabletop flows.

**Non-Goals:**
- This design MUST NOT introduce broad automatic currency reconciliation from arbitrary prose.
- This design MUST NOT change character schema, save format, or persistence APIs.
- This design SHOULD NOT widen the validator into a generic semantic parser for every adjudication nuance.

## Decisions

### Decision: Use a fail-closed bookkeeping guard instead of auto-repair
- **Decision:** Runtime MUST reject explicit currency/inventory bookkeeping corrections that claim committed state without executable character-update actions.
- **Rationale:** The user-visible failure is worse when prose silently claims Python state changed. A narrow fail-closed guard preserves mechanical truth without inventing new state mutations from ambiguous prose.
- **Alternative considered:** Auto-infer `currency_delta` and `inventory_remove` actions from correction language. Rejected for this slice because correction turns are often conversational and can be ambiguous about quantity, owner, or reversal scope.

### Decision: Put the new guard before validation skip routing
- **Decision:** Detection MUST run before `should_skip_llm_validation(...)` can classify the turn as `narration_only`.
- **Rationale:** The current bug is caused by the low-risk skip path finalizing a bad response before the LLM validator sees it. Runtime must block that fast-path early.
- **Alternative considered:** Rely on prompt changes alone. Rejected because prompt drift caused the bug and prompt-only fixes are not sufficient for a mechanical truth invariant.

### Decision: Keep detection narrow and explicit
- **Decision:** The deterministic guard MUST target explicit bookkeeping-correction/mutation language only: correction, payment, refund, gain/loss, coin transfer, or inventory-vs-currency reclassification claims.
- **Rationale:** Narrow detection reduces false positives on pure DM explanations such as "coins are usually tracked as currency" when no committed sheet change is being claimed.
- **Alternative considered:** Flag all turns mentioning coins, purses, or inventory. Rejected because that would over-block lawful clarification and lore/rules Q&A.

### Decision: Treat prompt parity as a supporting layer, not the authority layer
- **Decision:** Prompt and validator updates SHOULD clarify that ruling-only answers may use `actions: []`, but any claimed bookkeeping correction MUST include `updateCharacterInfo`.
- **Rationale:** Prompt parity reduces recurrence and helps the validator give better correction text, but Python remains the authoritative enforcement layer.
- **Alternative considered:** Leave prompts unchanged and fix runtime only. Rejected because the existing examples still blur currency and inventory semantics and would continue to teach the wrong behavior.

## Risks / Trade-offs

- **False positives on pure clarifications** -> Mitigation: detection MUST require explicit committed-change phrasing, not general rules explanation alone.
- **Prompt/runtime drift after change** -> Mitigation: add source-contract regressions for compressed prompt and validator wording.
- **Overly permissive fallback remains in uncompressed prompt variants** -> Mitigation: mirror the same contract in compressed and uncompressed prompt layers where relevant.
- **Builder over-expands scope into general financial reconciliation** -> Mitigation: tasks MUST keep this slice fail-closed and avoid auto-repair for ambiguous prose.

## Migration Plan

1. Add the deterministic bookkeeping-correction guard and wire it into narrator validation before skip routing.
2. Tighten skip routing so explicit bookkeeping-correction turns cannot take the `narration_only` path.
3. Update compressed prompt/validator wording and examples to separate ruling-only clarification from committed bookkeeping mutation.
4. Add targeted regressions for skip routing, deterministic guard behavior, and prompt source contracts.

Rollback strategy:
- Revert the new deterministic guard and skip-routing exclusion together if false positives are observed.
- Prompt wording can be rolled back independently, but runtime guard rollback MUST be deliberate because it reopens silent state-drift risk.

## Open Questions

- Should a future follow-up add safe auto-repair for uniquely unambiguous currency corrections, similar to item-transfer recovery?
- Should authoritative currency-query handling grow into its own runtime helper, parallel to `inventory_possession_authority`, or remain part of deterministic validation for now?
