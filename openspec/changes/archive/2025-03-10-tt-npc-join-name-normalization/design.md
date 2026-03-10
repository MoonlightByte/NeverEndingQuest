## Context

`main.py` currently normalizes NPC names only for `updateCharacterInfo` actions before validation. Party-join actions (`updatePartyNPCs`) and NPC movement actions (`moveBackgroundNPC`) do not pass through equivalent canonicalization in the pre-validation phase.

At the same time, validation context enforces strict full-name usage for NPC action fields. This mismatch can reject semantically valid outputs (`"Kira"` vs `"Scout Kira"`) and trigger correction loops.

Constraints:
- MUST preserve deterministic fail-closed behavior for ambiguous identity.
- MUST preserve backward compatibility with single-player and upstream flow.
- MUST keep TABLETOP MODE boundaries minimal and explicit.

## Goals / Non-Goals

**Goals:**
- Ensure party-NPC action names are canonicalized deterministically before LLM validation.
- Keep alias behavior consistent across narration mention detection and action payload checks.
- Prevent Kira-style onboarding failures caused by short-name payloads.
- Align prompt examples and validation instructions with runtime behavior.

**Non-Goals:**
- No redesign of arrival validator architecture.
- No schema migrations.
- No relaxed acceptance of unknown NPC identities.

## Decisions

### Decision 1: Add pre-validation canonicalization for party-NPC action payloads
- MUST: Extend the existing pre-validation normalization pass in `main.py` to cover:
  - `updatePartyNPCs` (`npc.name` object form and list/string variants)
  - `moveBackgroundNPC` (`npcName`)
- MUST: Use the same canonical identity source (`partyMembers`, `partyNPCs`, known module NPCs where needed) and unambiguous matching semantics.
- SHOULD: Reuse shared normalization helpers instead of duplicating parsing logic.

Alternatives considered:
- Prompt-only fix: rejected (non-deterministic and already drift-prone).
- LLM validator-only tolerance: rejected (still allows deterministic/runtime mismatch).

### Decision 2: Keep ambiguity fail-closed
- MUST: If short-name mapping yields multiple candidates, reject with explicit reason and do not auto-choose.
- SHOULD: Emit concise debug markers for ambiguous candidate sets.

Alternatives considered:
- Best-guess winner by lexical distance: rejected (unsafe identity mutation risk).

### Decision 3: Enforce prompt/runtime contract parity
- MUST: Replace contradictory short-name examples in compressed prompts where action payloads are intended to be canonical.
- MUST: Keep explicit clause that short narration mention is valid when action canonical name is correct.
- SHOULD: Add a source-level regression that guards against short-name examples in canonical action sections.

Alternatives considered:
- Leave examples as-is and rely on validator corrections: rejected (causes avoidable retries).

## Risks / Trade-offs

- [Over-normalization maps wrong NPC] -> Keep unambiguous-only mapping and fail-closed ambiguity.
- [Prompt edits cause wider behavior drift] -> Scope edits to NPC join/arrival sections only; no broad formatting churn.
- [Single-player regression] -> Gate normalization behavior to existing data contracts and run current validation suites.

## Migration Plan

1. Implement canonicalization for `updatePartyNPCs`/`moveBackgroundNPC` pre-validation paths in `main.py`.
2. Extend shared name normalization helper(s) where necessary, preserving existing `updateCharacterInfo` behavior.
3. Update compressed prompt examples/instructions for canonical action-name parity.
4. Add/extend regression tests for:
   - short-name join payload normalization (`Kira` -> `Scout Kira`)
   - ambiguous short-name failure
   - prompt/runtime contract consistency.
5. Run compile + targeted validation tests.

Rollback strategy:
- Revert prompt edits first if only prompt drift is detected.
- Revert new normalization branches in `main.py` while preserving tests to isolate root cause.
- Keep ambiguity fail-closed behavior intact during rollback.

## Open Questions

- Should module-wide NPC codex resolution be included in pre-validation canonicalization for `updatePartyNPCs`, or restricted to party-visible identities only?
- Should correction messages surface candidate suggestions for ambiguous names, or remain generic for safety?
