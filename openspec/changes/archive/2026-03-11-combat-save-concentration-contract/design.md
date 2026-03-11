## Context

The repo already has global `requestRoll` and concentration DC scaffolding from the prompt-validator hardening work, and combat runtime includes parser-side validation hooks for `requestRoll`. What combat still lacks is prompt/validator alignment: multi-PC combat prompts continue to teach prose-era save/check pauses and loose concentration wording instead of consistently preferring the structured pause contract.

This change is intentionally combat-specific. It does not redefine the global contract. It applies that contract to the combat prompt/validator surface with narrow tests and only minimal runtime alignment if inspection proves one is needed.

## Goals / Non-Goals

**Goals:**
- Prefer `requestRoll` in combat for saving throws, ability checks, skill checks, and concentration saves.
- Preserve stop-after-request semantics.
- Lock combat concentration DC wording to `max(10, floor(damage / 2))`.
- Preserve prose-only compatibility during migration.
- Keep the rollout test-first and merge-safe.

**Non-Goals:**
- No full dice engine.
- No automatic roll-result application.
- No combat initiative or round-flow rewrite.
- No enemy-side contract widening.
- No deprecation of prose-only save/check narration in this change.

## Decisions

### Decision 1: Combat prefers `requestRoll`, not prose-only requests

**Decision:** The combat prompt and combat validator SHALL prefer `requestRoll` for player-facing saving throws, ability checks, skill checks, and concentration saves.

**Rationale:** Combat now has structured PC/allied state routing. Save/check pauses should use the same explicit contract style instead of remaining prose-only.

### Decision 2: `requestRoll` remains a pause contract in combat

**Decision:** When a combat response emits `requestRoll`, that response SHALL stop after issuing the request and SHALL NOT narrate contingent success/failure outcomes in the same response.

**Rationale:** This preserves current tabletop pause semantics and prevents accidental dice-engine behavior.

### Decision 3: Combat concentration requests use one deterministic formula

**Decision:** Combat concentration save requests SHALL use `max(10, floor(damage / 2))`.

**Rationale:** The formula already exists as the canonical 5e rule and should be surfaced consistently in combat prompt/validator guidance.

### Decision 4: Prose compatibility remains during migration

**Decision:** Prose-only save/check requests SHALL remain compatibility-valid during this change.

**Rationale:** Existing combat examples and sessions still use prose requests. Narrow migration reduces risk.

### Decision 5: Runtime edits are optional and evidence-driven

**Decision:** Runtime files SHALL change only if combat-specific inspection reveals a real gap between current `requestRoll` scaffolding and the combat contract.

**Rationale:** `core/ai/action_handler.py` and `core/managers/combat_manager.py` already contain scaffolding. The likely missing piece is prompt/validator alignment, not parser design.

## Risks and Mitigations

- **Risk:** Builders accidentally widen scope into roll resolution.
  - **Mitigation:** Tasks and builder prompts explicitly forbid resolution logic.
- **Risk:** Combat prompt and validator drift.
  - **Mitigation:** Contract-first combat-specific tests lock parity before implementation broadens.
- **Risk:** Concentration wording drifts away from deterministic DC expectations.
  - **Mitigation:** Add dedicated combat contract tests for the formula and pause behavior.
- **Risk:** Existing combat prose requests break.
  - **Mitigation:** Keep prose compatibility explicit in prompt and validator wording.

## Migration Plan

### Phase 1 - Contract locks and tests
- Add focused combat contract tests for `requestRoll` preference, pause semantics, prose compatibility, and concentration DC expectations.
- Do not change prompt/runtime behavior yet.

### Phase 2 - Combat prompt and validator alignment
- Update compressed combat prompt and compressed combat validator to prefer `requestRoll`.
- Update mirror combat prompt files only as needed for parity/docs.

### Phase 3 - Narrow runtime alignment
- Inspect `core/managers/combat_manager.py` and `core/ai/action_handler.py` for any combat-specific gap.
- Apply only minimal edits if a real gap is found.
- Otherwise close the runtime step as a no-op.

### Phase 4 - Verification
- Run targeted combat contract tests, existing save/concentration tests, combat regressions, syntax checks if needed, and `openspec validate`.

## Rollback Strategy

- Revert combat prompt/validator `requestRoll` preference edits first.
- Preserve existing global `requestRoll` and concentration helper scaffolding unless the regression is clearly runtime-rooted.
- Keep enemy-side combat mutation contracts unchanged throughout.
