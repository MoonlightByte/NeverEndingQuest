## Context

The current UI hides the Saving Throws section unless `savingThrows` is non-empty, which makes some characters appear incomplete even though ability modifiers exist. At the same time, export code performs proficiency checks using lowercase ability keys, while many character files store proficiencies in title-case ability names. This mismatch causes display/export divergence.

## Goals / Non-Goals

**Goals:**
- Ensure saving throw proficiency matching is canonical and case-insensitive.
- Ensure the GUI always displays six saving throws.
- Provide class-based fallback proficiencies when data is missing.
- Keep behavior deterministic and independent of chat/LLM.

**Non-Goals:**
- No new schema fields.
- No changes to initiative/combat logic.

## Decisions

### 1) Canonical proficiency normalization helper
Decision: Add one shared helper to normalize `savingThrows` into canonical lowercase ability keys:
- accepted input forms: `Strength`, `strength`, `STR`, `dexterity`, etc.
- output: set/list of `strength|dexterity|constitution|intelligence|wisdom|charisma`

Rationale:
- Removes repeated casing logic and prevents future drift.

### 2) Deterministic fallback by class when empty
Decision: If normalized `savingThrows` is empty, derive fallback from class name (case-insensitive), including alias support (`thief` -> rogue mapping).

Rationale:
- Preserves useful behavior for legacy/partial sheets without hiding panel.

### 3) GUI always renders saving throw panel
Decision: Remove panel gating on `savingThrows.length > 0`; always render six entries and use normalized/fallback proficiency markers.

Rationale:
- Stable UX and immediate visibility of save bonuses.

### 4) PDF export uses same normalized/fallback source
Decision: Route PDF proficiency check + checkboxes through the same normalized/fallback helper.

Rationale:
- Ensures GUI and PDF consistency.

## Risks / Trade-offs

- [Class parsing edge cases] -> Mitigation: map common aliases and default to no proficiency if unknown class.
- [Legacy weird values in `savingThrows`] -> Mitigation: ignore unknown tokens, log once.
- [Data mutation concerns] -> Mitigation: fallback can be render-time only; optional explicit backfill tool for persistence.

## Migration Plan

1. Add normalization/fallback helper.
2. Integrate helper into GUI rendering logic.
3. Integrate helper into PDF export mapping.
4. Add optional one-time backfill script for existing files.
5. Verify affected and regression characters.

## Open Questions

- Should fallback values be persisted to character files automatically, or only used at render/export time unless explicit backfill is run?
