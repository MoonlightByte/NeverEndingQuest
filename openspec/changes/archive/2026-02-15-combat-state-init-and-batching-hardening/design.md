## Context

Observed failures are not isolated bugs; they are coupled by one state-consistency problem:

- Narrator lane can continue when combat lane initialization fails.
- Slash-command handling can bypass combat lane assumptions in narrative mode.
- Initiative and enemy-phase logic become unreliable when the current state is ambiguous.

The design prioritizes deterministic state transitions over prompt-only corrections.

## Goals / Non-Goals

**Goals:**
- Ensure combat commitment fails closed unless formal encounter state is valid.
- Ensure combat-only slash commands are routed only in active combat context.
- Ensure Phase 1 two-group initiative startup is consistently authoritative.
- Ensure enemy/NPC batching can target all valid PCs without actor-integrity false rejects.

**Non-Goals:**
- Rework full combat simulation prompt strategy.
- Add new combat command semantics.
- Introduce schema-breaking encounter format changes.

## Decisions

1. **Fail-closed on combat entry and post-validation fallback**
   - Decision: if combat setup/validation fails, do not execute fallback narration as canonical combat progression.
   - Rationale: prevents desync where users observe combat narration without engine-backed combat state.

2. **Guard combat-only commands in narrative loop**
   - Decision: block `/init`, `/end`, `/att`, `/dmg` and related combat-only commands when no active encounter is present.
   - Rationale: prevents narrator-path handling of commands that require combat-manager context.

3. **Normalize initiative startup state at runtime**
   - Decision: add a normalization/backfill step for encounter initiative fields used by Phase 1 two-group flow.
   - Rationale: stabilizes startup behavior for mixed/legacy encounters without regressing in-progress rounds.

4. **Separate actor validity from target validity in enemy phase**
   - Decision: keep PCs forbidden as DM-controlled actors, but explicitly valid as targets for enemy/NPC actions and damage updates.
   - Rationale: resolves "no attacks on PCs" failure caused by over-strict integrity assumptions.

## Risks / Trade-offs

- [Risk: over-blocking commands] -> Use explicit combat-only command list and clear system guidance.
- [Risk: legacy encounter regressions] -> Normalize only missing Phase 1 fields, avoid overwriting valid in-progress state.
- [Risk: validation drift] -> Add focused regression tests covering fail-closed and integrity pathways.

## Migration Plan

1. Apply fail-closed guards in combat entry and action-handler failure returns.
2. Add narrative-loop combat command routing guards.
3. Add initiative normalization for Phase 1 two-group startup.
4. Align enemy-batch actor collection and integrity validation for PC-target updates.
5. Add and run regression tests.

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile main.py core/ai/action_handler.py core/managers/combat_manager.py core/managers/multi_pc_combat.py`
- Tests:
  - `python3 scripts/test_multi_pc_combat.py`
  - focused regression tests for command routing and fail-closed combat entry (existing suite extension or new script)
- Manual smoke sequence:
  - Trigger encounter creation failure -> confirm no combat narration continuation.
  - Use `/init` and `/end` outside combat -> confirm deterministic system guidance.
  - Start combat -> confirm `/init <1-20>` gate and winner resolution.
  - Trigger enemy phase -> confirm PCs can be valid damage targets.
