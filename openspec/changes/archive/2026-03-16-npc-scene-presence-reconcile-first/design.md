## Context

The current NPC validator is still organized around arrival policing. It allows foreshadowing and incidental references, but when narration explicitly presents a known NPC in-scene without matching `moveBackgroundNPC` or `updatePartyNPCs`, runtime hard-fails immediately. That is still too brittle for the gametest target balance defined in `plans/archive/llm-wants-to-be-free.md`: narrator-loose, reconcile-first, mechanically strict.

G3 should therefore be the smallest possible conversion from arrival policing to scene-presence reconciliation. It should not become a full world-delta system. It should only cover the worst immersion-breaking loops where one clear canonical NPC is presented as physically present in the current scene, identity is safe, and durable party membership is not implied.

Constraints:
- Keep this slice narrower than travel reconciliation.
- Preserve party-membership durability rules.
- Preserve ambiguity fail-safe behavior.
- Preserve explicit action support when present.
- Keep host-file integration additive and marked with `# TABLETOP MODE:` comments.

## Goals / Non-Goals

**Goals:**
- Allow explicit-but-safe scene presence to reconcile instead of hard-failing.
- Preserve foreshadowing and informational mentions as action-free.
- Preserve explicit `updatePartyNPCs` for party joins.
- Preserve identity safety for ambiguous NPC references.
- Lock transcript-driven expectations before runtime implementation.

**Non-Goals:**
- No event ledger or background world evolution.
- No broad prompt-stack rewrite in this slice.
- No global validator redesign in this slice.
- No new durable NPC lifecycle model beyond scene presence vs party membership distinction.

## Decisions

### Decision 1: Reconcile-first applies only to clear, scene-compatible NPC presence

The runtime SHALL only reconcile NPC presence when narration clearly presents one canonical NPC as present in the current scene and that presence is safe to commit.

Rationale:
- Keeps scope narrow for the gametest lane.
- Avoids silently broadening into generic NPC movement inference.

Alternative considered:
- Reconcile every explicit arrival mention automatically.
- Rejected as too broad and likely to commit wrong canon.

### Decision 2: Scene presence is distinct from party membership

This change SHALL distinguish a scene-present NPC from a durable party-member NPC.

Rationale:
- The plan explicitly calls for distinguishing scene presence from durable party membership.
- Party membership affects longer-lived persistence and should remain explicit.

Alternative considered:
- Treat any reconciled scene presence as equivalent to party membership.
- Rejected because it would over-commit state from narrative flavor alone.

### Decision 3: Foreshadowing and informational references remain action-free

The current legal behavior for rumors, memories, distant references, and off-location descriptive mentions SHALL remain intact.

Rationale:
- This behavior already restores some narrator breathing room and should not regress.

Alternative considered:
- Revisit all mention classes at once.
- Rejected as unnecessary expansion.

### Decision 4: Ambiguous identity remains fail-safe

If scene presence cannot be mapped safely to one canonical NPC identity, runtime SHALL not auto-commit that presence.

Rationale:
- Wrong canon is worse than delayed canon.
- The plan explicitly preserves ambiguity safety.

Alternative considered:
- Best-guess reconciliation from short aliases.
- Rejected as too risky before testers.

### Decision 5: Explicit action paths remain authoritative when present

If narration already includes a valid explicit movement or party-membership action, runtime SHALL continue to honor that explicit action path.

Rationale:
- Keeps the change additive and compatible with current schema behavior.

## Risks / Trade-offs

- [Risk] Scene-presence reconciliation could over-commit NPC movement.
  -> Mitigation: only reconcile one clear canonical NPC in scene-compatible contexts; keep joins explicit.

- [Risk] Party-membership semantics could blur.
  -> Mitigation: keep `updatePartyNPCs` mandatory for true join cases.

- [Risk] Existing validator language could still fight the new runtime.
  -> Mitigation: modify the touched narrator-validation contract only for the reconciled domain.

## Migration Plan

1. Add transcript-driven regression tests that describe the intended G3 behavior before runtime changes.
2. Add OpenSpec contract artifacts for scene-presence reconciliation and validation authority narrowing.
3. Implement narrow reconciliation logic in the validator/runtime path only after review.
4. Verify that explicit joins still require explicit persistence actions.

Rollback strategy:
- If scene-presence reconciliation proves unstable, revert runtime inference while keeping the narrower contract/tests for future work.

## Open Questions

- Whether the narrowest safe G3 implementation should infer `moveBackgroundNPC` directly or introduce a local intermediate classification before action injection.
- Whether an initial implementation should reconcile only one explicit NPC per turn and defer multi-NPC scene-presence turns.
