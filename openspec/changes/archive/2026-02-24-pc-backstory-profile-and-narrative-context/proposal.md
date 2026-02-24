## Why

The portrait Create modal currently requires `backgroundFeature.name` and `backgroundFeature.description`, but those fields now map to PDF page 2 `Feat+Traits` (Additional Features and Traits), not to narrative backstory.

We need a first-class `backstory` field in character JSON so players can author or edit narrative history directly, and so that history can influence portrait generation and runtime narrative flavor.

## What Changes

- Add `backstory` to character schema and normalization defaults.
- Add `backstory` capture and validation across PC generation paths:
  - Roll Your Own (`/api/party/create_manual`)
  - Create with DM final JSON validation (`/api/party/finalize_creation` and DM interview prompt contract)
  - Startup/fallback character creation defaults
- Replace portrait Create modal background-feature inputs with a required `Backstory` textarea.
- Update portrait create API payload parsing/persistence to use `backstory`.
- Update portrait prompt composition so `backstory` influences generated image context.
- Extend readiness/profile audit and readiness repair to include `backstory`.
- Extend narrative context surfaces (DM/combat/system context formatting) so `backstory` is available for event flavor.
- Define NPC -> PC promotion behavior for missing `backstory` as warning-first (non-blocking).
- Update PDF Backstory population contract to prefer authored `backstory` (optionally with recent-adventures append).

### MUST Contract

- MUST add `backstory` without breaking legacy character files.
- MUST preserve existing `backgroundFeature` semantics and mappings.
- MUST replace portrait modal background-feature fields with backstory field.
- MUST include `backstory` in shared audit/readiness/repair contracts for PC workflows.
- MUST keep promotion flow non-destructive and identity-preserving.
- MUST keep SP and TT compatibility.

### SHOULD Guidance

- SHOULD treat `backstory` as PC-critical and NPC-warning-only by default.
- SHOULD bound `backstory` text when injected into LLM contexts to avoid token sprawl.
- SHOULD preserve merge-safe host edits and `# TABLETOP MODE:` markers where relevant.

### Non-goals

- No interim stopgap fields that will be replaced by later world-narrative build.
- No changes to 5e mechanics/state enforcement.
- No schema-breaking migration requiring bulk rewrite of all existing character files.

## Capabilities

### New Capabilities

- `pc-backstory-narrative-context`

### Modified Capabilities

- `tt-pc-creation-workflows`
- `character-sheet-completeness-audit`
- `tt-character-readiness-repair`
- `background-feature-guided-entry-ux`

## Impact

- Affected code (planned):
  - `schemas/char_schema.json`
  - `utils/character_creation_audit.py`
  - `utils/startup_wizard.py`
  - `web/templates/partials/character_tabs.html`
  - `web/static/js/tabletop_mode.js` (payload passthrough only)
  - `prompts/character_creation/dm_interview_prompt.txt`
  - `web/templates/game_interface.html` (portrait profile modal)
  - `web/web_interface.py` (portrait create profile contract)
  - `core/toolkit/portrait_service.py`
  - `core/ai/conversation_utils.py`
  - `core/managers/combat_manager.py`
  - `utils/multi_pc_dm_note.py`
  - `core/ai/character_sheet_compressor.py`
  - `web/routes/tabletop_party_routes.py` (creation + promotion warning behavior)
  - `web/routes/character_sheet_routes.py` (PDF Backstory field preference)
  - `scripts/test_character_creation_audit.py`
  - `scripts/test_pc_image_create_mvp.py`
- Rollout risk: Medium (cross-cutting profile contract updates).
- Fallback strategy:
  - Keep `backstory` optional at schema level while enforcing completeness in PC flows.
  - Preserve fail-open warnings for legacy NPC/promotion data.
