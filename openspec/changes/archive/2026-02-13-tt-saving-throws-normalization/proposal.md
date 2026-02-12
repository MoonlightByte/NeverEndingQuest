## Why

Saving throw presentation is inconsistent between character sheets and PDF exports. In the web GUI, the Saving Throws panel disappears when `savingThrows` is empty. In export logic, proficiency matching can fail when data uses title-case values (for example `"Intelligence"`) while checks use lowercase keys. This produces confusing UX where some PCs appear to have no saving throw data despite usable stats.

## What Changes

- Normalize saving throw proficiency handling to be case-insensitive across GUI and PDF paths.
- Always render the Saving Throws panel in the web character sheet (show all six saves, with proficiency markers).
- Add deterministic class-based fallback saving throw proficiencies when `savingThrows` is empty.
- Align PDF proficiency/checkbox mapping with normalized proficiency values.
- Add optional backfill utility/task for existing character files with empty `savingThrows`.
- Add focused verification scenarios for affected characters (Tester, Xerxes, Cyrius) and regression checks for already-valid characters (Acheron, Claris).

Explicit non-goals:
- No changes to combat calculations.
- No schema format changes for character files.
- No LLM prompt or repair-flow modifications.

## Capabilities

### New Capabilities
- `tt-saving-throws-consistency`: Deterministic, normalized saving throw rendering/export behavior for all PCs.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `web/templates/game_interface.html`
  - `web/routes/character_sheet_routes.py`
  - `utils/character_creation_audit.py` or a dedicated helper for normalization/fallback rules
  - optional script for one-time character backfill
- APIs/endpoints:
  - No new endpoints required.
- Rollout risk: low-medium (display/export logic), mitigated by narrow scope and explicit regression checks.
- Compatibility:
  - Backward compatible with existing character schema and SP/TT flows.
