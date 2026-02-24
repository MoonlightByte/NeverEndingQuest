## Why

The character sheet currently exposes `Download PDF` but does not provide a direct in-sheet edit entry.
Facilitators must navigate to Manage Party and manually reuse Roll Your Own fields, which is slow during live tabletop play.

We need a deterministic `Edit` button in the character sheet so players can edit their PC at any time using the existing Roll Your Own form.

## What Changes

- Add an `Edit` button in the character sheet action row, positioned before `Download PDF` on one line.
- Wire `Edit` to open the existing Roll Your Own modal/tab with active PC data prefilled.
- Add a dedicated manual edit endpoint for existing PCs (for example `/api/party/update_manual`) that:
  - loads the existing character file,
  - applies form-backed updates,
  - runs shared audit validation,
  - saves deterministically with atomic write helpers.
- Reuse the existing Roll Your Own form and JS flow with mode switching (`create` vs `edit`) instead of creating a second edit modal.

MUST constraints:
- MUST place `Edit` before `Download PDF` in one row in the character sheet UI.
- MUST open the existing Roll Your Own form for edit, not a new divergent form.
- MUST update the existing PC file only (no new file creation, no party membership changes).
- MUST run shared audit/validation before write; failed audit blocks save.
- MUST keep this flow deterministic and not route through LLM-driven `updateCharacterInfo`.
- MUST preserve SP/TT compatibility and existing create flow behavior.

SHOULD guidance:
- SHOULD make name read-only in edit mode to avoid rename side effects in MVP.
- SHOULD preserve non-form fields (including complex spell/feature structures) when applying edits.
- SHOULD keep host edits minimal and mark required host hooks with `# TABLETOP MODE:`.

### Non-goals

- No free-form natural-language edit parsing.
- No rename/move character-file workflow in this change.
- No schema-breaking migration.
- No combat or narration rule changes.

## Capabilities

### New Capabilities

- `tt-character-sheet-manual-edit`

### Modified Capabilities

- `tt-pc-creation-workflows`
- `character-sheet-completeness-audit`

## Impact

- Affected code (planned):
  - `web/templates/game_interface.html`
  - `web/static/js/tabletop_mode.js`
  - `web/routes/tabletop_party_routes.py`
  - `scripts/test_pc_image_create_mvp.py` (or equivalent focused tests)
- Rollout risk: Low to medium (UI-to-route wiring and save contract).
- Fallback strategy:
  - Keep create path unchanged.
  - If edit validation fails, return structured errors and keep character file unchanged.
- Merge-safety/SP-MP impact:
  - Additive and merge-safe.
  - Same deterministic behavior in single-player and tabletop modes.
