## Context

The combat refactor is now structurally consistent everywhere except enemy-side mutation routing. Prompt authority, validation slimming, touched-combatant truth packs, structured PC/allied updates, save/check pause contracts, and bounded deterministic guards are already in place. Enemy-side combat mutations still lean on prose-heavy `updateEncounter.changes`, which leaves monsters as the last major mechanics surface not yet aligned with the Python-owned legality model.

This second-wave slice is intentionally narrow. It is the capstone needed to complete the planned combat prompt/validation refactor without turning the deferred work into a full encounter-engine rewrite.

## Goals / Non-Goals

**Goals:**
- Prefer mixed `changes + ops` payloads for enemy-side `updateEncounter` mutations in combat.
- Preserve prose compatibility during migration.
- Keep the routing boundary between enemy `updateEncounter` mutations and PC/allied `updateCharacterInfo` mutations.
- Limit the first-wave enemy op family to HP, status, and condition updates.
- Add combat-specific tests so future prompt or runtime edits do not regress the enemy-side contract.

**Non-Goals:**
- No spawn/despawn encounter ops.
- No initiative reorder or queue rebuild ops.
- No battlefield topology ops.
- No hard deprecation of prose-only enemy updates.
- No roll-resolution redesign.
- No broad combat manager rewrite.

## Decisions

### Decision 1: Combat uses mixed encounter payload preference, not `ops`-only hardening

**Decision:** Combat prompt and validator guidance SHALL prefer `updateEncounter` payloads that include both `changes` and supported `ops` for enemy-side mutations.

**Rationale:** Mixed payloads preserve readability and backward compatibility while allowing runtime to apply deterministic enemy mechanics from `ops`.

### Decision 2: Supported enemy `ops` are authoritative when present

**Decision:** When supported enemy encounter `ops` are present, runtime SHALL treat them as the authoritative mechanics payload for that mutation.

**Rationale:** The purpose of this slice is to reduce prose-only enemy mechanics interpretation, not merely to add another mirror field.

### Decision 3: First-wave enemy op family stays intentionally small

**Decision:** The approved first-wave enemy op family SHALL be limited to:
- `hp_delta`
- `set_hp`
- `condition_add`
- `condition_remove`
- `set_status`

**Rationale:** These cover the highest-value and most common enemy combat state mutations without widening into encounter-engine behavior.

### Decision 4: Routing boundary remains explicit and enforced

**Decision:** Enemy-side combat mutations SHALL remain on `updateEncounter`, while PC/allied mutations SHALL remain on `updateCharacterInfo`.

**Rationale:** Workstream I is intended to complete contract symmetry, not blur state ownership boundaries.

### Decision 5: Unsupported or ambiguous enemy ops fail open to safe fallback

**Decision:** Unsupported, partial, or ambiguous enemy ops payloads SHALL preserve prose fallback behavior instead of forcing brittle deterministic handling.

**Rationale:** This keeps the migration safe and aligns with the repo's fail-open philosophy where certainty is absent.

### Decision 6: Runtime edits stay narrow and evidence-driven

**Decision:** Runtime files SHALL change only if contract coverage reveals a real gap in `core/ai/action_handler.py` or `updates/update_encounter.py`.

**Rationale:** Prompt/validator contract alignment is the main missing piece. Runtime should not widen unless tests prove it is required.

## Risks and Mitigations

- **Risk:** Workstream I expands into a broad encounter-engine rewrite.
  - **Mitigation:** Lock scope to enemy HP, status, and condition ops only.
- **Risk:** Enemy encounter ops drift into PC/allied routing semantics.
  - **Mitigation:** Add explicit tests that preserve `updateEncounter` vs `updateCharacterInfo` routing separation.
- **Risk:** Prompt examples teach unsupported enemy op shapes.
  - **Mitigation:** Restrict examples and tests to the approved first-wave enemy op family.
- **Risk:** Prose fallback is removed before runtime confidence exists.
  - **Mitigation:** Keep `changes` compatibility-valid throughout this slice.

## Migration Plan

### Phase 1 - Contract locks
- Add focused combat contract tests for enemy-side mixed payload preference and routing separation.
- Add explicit coverage for the approved first-wave enemy op family.
- No runtime changes yet.

### Phase 2 - Combat prompt and validator alignment
- Update compressed combat prompt and compressed combat validator wording/examples to prefer enemy `changes + ops` payloads.
- Update mirror prompt files only as needed for docs/parity.

### Phase 3 - Narrow runtime alignment
- Inspect `core/ai/action_handler.py` and `updates/update_encounter.py` for encounter-ops routing gaps.
- If needed, add only narrow deterministic handling for the approved first-wave enemy ops.
- Preserve prose fallback for unsupported or ambiguous ops.

### Phase 4 - Verification
- Run targeted contract tests and existing combat regressions.
- Validate the OpenSpec change.

## Rollback Strategy

- Revert prompt/validator encounter-ops preference edits first.
- Revert any narrow encounter-ops runtime fast path before touching older prose fallback behavior.
- Preserve routing separation and prose compatibility throughout rollback.
