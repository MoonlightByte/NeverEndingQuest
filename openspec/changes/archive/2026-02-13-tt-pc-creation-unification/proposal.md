## Why

TABLETOP MODE character creation currently uses mixed paths (startup wizard, web DM interview, manual quick-create, and add-existing) with inconsistent validation and completeness guarantees. This causes partial character sheets, unreliable PDF exports, and friction for real tabletop sessions that need multi-PC onboarding at campaign start and mid-campaign.

## What Changes

- Add a unified character creation contract shared by all PC creation paths: canonical defaults, schema validation, and completeness audit against `schemas/char_schema.json`.
- Add deterministic post-create audit for all creation modes (startup, Create with DM, Roll Your Own, Add Existing onboarding checks) before party insertion.
- Extend startup flow to support iterative multi-player campaign initiation ("add another player" loop) while preserving single-player behavior.
- Filter `Add Existing` results to exclude PCs already in `partyMembers`, with dedupe across scanned locations.
- Harden `Create with DM` finalization to reliably parse final JSON, validate against schema, and recover when incomplete.
- Rename `DM Quick-Create` to `Roll Your Own` and align form sections with 5e character sheet structure.
- Add optional enrichment pass for narrative-only fields (for example `backgroundFeature.description`) without changing mechanical truth.
- Add acceptance-focused tests and smoke checks for all four tabletop PC creation scenarios.

Explicit non-goals:
- No combat-system, initiative, or encounter-logic changes.
- No rewrite of upstream single-player startup UX beyond compatibility-safe loop extensions.
- No schema-breaking character format changes.

## Capabilities

### New Capabilities
- `tt-pc-creation-workflows`: Unified tabletop-safe PC creation workflows for campaign initiation, mid-campaign joins, DM interview creation, and Roll Your Own manual creation.
- `character-sheet-completeness-audit`: Shared schema/completeness validation and post-create enrichment gates applied before character persistence and sheet/PDF usage.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `utils/startup_wizard.py`
  - `web/templates/partials/character_tabs.html`
  - `web/static/js/tabletop_mode.js`
  - `web/routes/tabletop_party_routes.py`
  - `main.py` (creation finalization path)
  - `utils/character_creator.py` and/or a new shared validation helper module
  - `web/templates/game_interface.html` (label + creation flow wiring)
  - `web/routes/character_sheet_routes.py` (readiness audit hook, non-breaking)
- APIs/endpoints:
  - Existing party creation endpoints remain, but behavior is tightened for filtering, validation, and error reporting.
- Dependencies/systems:
  - Reuses existing JSON schema validation stack (`jsonschema`) and atomic file operations.
- Rollout risk: medium (touches startup, web routes, and creation finalization).
  - Mitigation: staged rollout by scenario, strict schema gate, and fallback to current behavior when loop/additional fields are not requested.
- Fallback strategy:
  - If multi-PC startup loop fails, complete with first valid PC (SP-compatible) and continue campaign startup.
  - If DM interview final JSON is invalid, keep creation mode active and request corrected JSON with explicit missing fields.
- Merge-safety/SP-MP compatibility:
  - Preserve upstream-compatible flow and keep hooks minimal with `# TABLETOP MODE:` markers in host files.
  - Maintain full backward compatibility for single-player mode.
