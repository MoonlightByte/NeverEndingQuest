## Why

Tabletop sessions often elevate a beloved NPC into a player-controlled character. Current Add Existing flow only targets players, while NPC promotion behavior is implicit and lacks explicit lifecycle tracking. We need a safe, explicit NPC -> PC promotion path that preserves memory continuity and future-proofs PC -> NPC retirement without implementing retirement UI in this change.

## What Changes

- Add explicit NPC companion promotion workflow in Manage Party Add Existing UI.
- Keep one canonical character identity/file during promotion (no duplicate PC/NPC files).
- Add stable `character_id` generation for promoted characters when missing.
- Add append-only `_tabletop_role_history` events for lifecycle traceability.
- Add backend promotion endpoint(s) with confirm flow and post-promotion audit/readiness checks.
- Preserve current active character on promotion (add without auto-switch).
- Maintain current player Add Existing behavior unchanged.

Explicit non-goals:
- No PC -> NPC retirement UI/flow implementation in this change.
- No combat logic changes.
- No schema-breaking character file migration.

## Capabilities

### New Capabilities
- `tt-npc-pc-role-lifecycle`: Explicit NPC companion promotion to PC with identity continuity and lifecycle event tracking.

### Modified Capabilities
- `tt-pc-creation-workflows`: Add Existing selection gains optional NPC companion source/promotion mode.

## Impact

- Affected code:
  - `web/templates/partials/character_tabs.html`
  - `web/static/js/tabletop_mode.js`
  - `web/routes/tabletop_party_routes.py`
  - `utils/pc_manager.py`
  - Optional helper module for lifecycle/identity utilities
- APIs/endpoints:
  - Existing character-list endpoint may gain source filtering mode and candidate metadata.
  - New promotion endpoint(s) for preview/apply confirmation.
- Rollout risk: medium (party state transitions), mitigated by explicit confirm, audit gates, and no auto active-character switch.
- Compatibility:
  - Backward compatible for existing player Add Existing flow and single-player behavior.
