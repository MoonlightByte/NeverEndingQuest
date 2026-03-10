## Context

The current system still routes many character sheet updates through prose `changes` strings. That keeps mechanics flexible, but it also preserves ambiguity, increases hallucination risk, and limits the gains from deterministic validation. The project is now ready for an additive structured mechanics pilot because:

- prompt/runtime contract drift has been reduced,
- deterministic guards exist for the highest-risk contradictions,
- validation routing is lighter and more observable,
- compact truth packs now ground validator state.

This change adds structured `ops` without removing the prose path.

## Goals / Non-Goals

**Goals:**
- Add additive `ops` support to `updateCharacterInfo.parameters`.
- Apply a first supported set of ops directly in Python.
- Preserve legacy `changes` fallback.
- Emit fallback telemetry when prose remains in use.

**Non-Goals:**
- No hard deprecation of prose `changes` yet.
- No new top-level action for mechanics in this phase.
- No full dice/save contract rewrite.
- No attempt to structure every possible character update in this phase.

## Decisions

### Decision 1: `ops` is additive, not replacing `changes`

**Decision:** `updateCharacterInfo.parameters` SHALL accept `ops` alongside `changes`, not instead of it.

**Rationale:** This preserves backward compatibility and allows gradual migration of narrator examples and runtime paths.

### Decision 2: Supported ops are validated and applied in Python

**Decision:** When supported `ops` are present, runtime SHALL validate and apply them directly before considering prose fallback.

**Rationale:** The main goal of the pilot is to reduce second-pass interpretation for common mechanics.

### Decision 3: Unsupported ops fail conservatively

**Decision:** Unsupported `ops` SHALL either fail deterministically or fall back only when the contract explicitly allows it and the payload still includes prose `changes`.

**Rationale:** Silent acceptance of unknown ops would weaken trust in the structured path.

### Decision 4: Fallback usage must be measurable

**Decision:** Legacy prose fallback SHALL emit deterministic usage markers so the project can measure migration progress.

**Rationale:** This is needed for later deprecation decisions.

### Decision 5: Initial scope stays narrow and high-value

**Decision:** The first pilot SHALL only include:
- `set_hp`
- `hp_delta`
- `spell_slot_delta`
- `inventory_add`
- `inventory_remove`
- `currency_delta`
- `condition_add`
- `condition_remove`

**Rationale:** These cover the most error-prone and most common sheet mutations.

## Risks and Mitigations

- **Risk:** Prompt examples may overuse unsupported ops.
  - **Mitigation:** Document only the supported initial set and keep prose fallback examples visible.
- **Risk:** Runtime application may diverge from existing freeform updater logic.
  - **Mitigation:** Add explicit application tests for each supported op type.
- **Risk:** Fallback behavior may mask missing support.
  - **Mitigation:** Emit deterministic fallback markers and keep unsupported ops conservative.

## Migration Plan

### Phase 1 - Contract and tests
- Add tests locking the `ops` contract across prompt/validator/runtime references.
- No runtime application changes yet.

### Phase 2 - Prompt and validator contract update
- Document `ops` in compressed prompt and validator contract.
- Keep legacy prose path documented as compatibility fallback.

### Phase 3 - Deterministic runtime application
- Add helper(s) to validate/apply supported ops.
- Integrate with `updateCharacterInfo` handling.

### Phase 4 - Fallback telemetry and mixed-mode verification
- Emit deterministic fallback markers when prose is used.
- Add mixed-mode tests for `changes`+`ops` payloads.

## Deferred Follow-Ups

- Extend ops coverage to XP/features/temp effects.
- Add narrator examples that prefer structured ops by default.
- Eventually tighten or deprecate prose-only high-risk updates after telemetry review.
