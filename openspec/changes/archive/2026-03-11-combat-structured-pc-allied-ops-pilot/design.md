## Context

The combat runtime now has a cleaner foundation after `combat-runtime-authority-and-efficiency`, but its PC/allied mutation contract still lags behind the rest of the refactor. Runtime already supports additive `updateCharacterInfo.ops` with deterministic application and fallback telemetry, yet combat prompt examples still teach prose-era updates for HP, spell slots, ammo spend, and conditions.

This change is intentionally narrow. It teaches combat to use the existing structured character-ops path more consistently without widening to enemy-side `updateEncounter.ops` or first-class save/check work.

## Goals / Non-Goals

**Goals:**
- Prefer mixed `changes + ops` payloads for combat PC/allied `updateCharacterInfo` actions.
- Preserve `changes` compatibility during migration.
- Keep enemy-side combat routing unchanged.
- Add combat-specific tests so future prompt edits do not regress the mixed payload contract.

**Non-Goals:**
- No `updateEncounter.ops` support.
- No combat `requestRoll` or concentration contract migration.
- No hard deprecation of prose-only updates.
- No broad combat manager rewrite.

## Decisions

### Decision 1: Combat uses mixed payload preference, not `ops`-only hardening

**Decision:** Combat prompt and validator guidance SHALL prefer `updateCharacterInfo` payloads that include both `changes` and `ops` for PC/allied mutations.

**Rationale:** Mixed payloads preserve narrative readability and backward compatibility while allowing runtime to apply deterministic mechanics from `ops`.

### Decision 2: `ops` is authoritative when present

**Decision:** When supported `ops` are present in combat-generated `updateCharacterInfo`, runtime SHALL continue treating `ops` as the authoritative mechanics payload.

**Rationale:** The purpose of this slice is to reduce prose-only mechanics interpretation, not merely to duplicate old prose examples.

### Decision 3: Enemy-side combat mutation contract remains unchanged

**Decision:** Enemy-side mutations SHALL remain on `updateEncounter` in this change.

**Rationale:** Deferring `updateEncounter.ops` keeps the change low-risk and aligned with the post-archive plan.

### Decision 4: Combat examples should target the highest-value mechanics first

**Decision:** Combat examples and tests SHALL focus first on:
- `hp_delta`
- `set_hp`
- `spell_slot_delta`
- `condition_add`
- `condition_remove`
- `inventory_remove` for ammo/consumable spend
- `inventory_add` where combat legitimately returns or grants an item

**Rationale:** These are the most common and highest-value combat-facing updates already supported by runtime.

### Decision 5: Runtime edits stay narrow and evidence-driven

**Decision:** Runtime files SHALL change only if combat contract coverage reveals a real routing or payload gap.

**Rationale:** The structured-ops engine already exists. Prompt/validator alignment is the main missing piece.

## Risks and Mitigations

- **Risk:** Combat prompts over-teach unsupported op patterns.
  - **Mitigation:** Lock examples to the existing supported ops set only.
- **Risk:** Mixed payload preference drifts into enemy-side contract widening.
  - **Mitigation:** Add explicit tests that enemy mutations remain on `updateEncounter`.
- **Risk:** Builders touch deep combat runtime logic unnecessarily.
  - **Mitigation:** Keep runtime scope narrow and require evidence before changing Python behavior.

## Migration Plan

### Phase 1 - Contract locks
- Add focused combat contract tests for mixed payload preference and enemy-side deferral.
- Do not change runtime behavior yet.

### Phase 2 - Combat prompt/validator alignment
- Update compressed combat prompt and compressed combat validator wording/examples.
- Update mirror prompt files only as needed for docs/parity.

### Phase 3 - Narrow runtime alignment
- Touch `core/ai/action_handler.py` or `updates/update_character_info.py` only if tests reveal a combat-specific gap.
- Preserve existing fallback telemetry markers.

### Phase 4 - Verification
- Run targeted contract tests and existing combat regressions.
- Validate the OpenSpec change.

## Rollback Strategy

- Revert combat prompt/validator mixed-payload preference edits first.
- Preserve the underlying structured-ops runtime engine and global ops contracts unless the regression proves runtime-rooted.
- Keep the enemy-side contract unchanged throughout rollback.
