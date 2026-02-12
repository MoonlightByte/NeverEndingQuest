## 1. Lifecycle and Identity Helpers

- [x] 1.1 Add helper(s) to ensure stable `character_id` exists for promotable records (verify: new ID generated once, preserved on repeat promotion attempts).
- [x] 1.2 Add helper(s) to append `_tabletop_role_history` events with timestamp and transition metadata (verify: append-only behavior).
- [x] 1.3 Add centralized role-normalization helper to set `type`, `character_type`, and `character_role` for promoted PCs (verify: all role markers updated consistently).

## 2. Backend Promotion API

- [x] 2.1 Extend Add Existing candidate endpoint(s) to support NPC companion source mode and candidate metadata (verify: current `partyNPCs` candidates appear; current party members excluded).
- [x] 2.2 Add promotion preview endpoint returning candidate summary + expected changes + readiness warnings (verify: no writes on preview).
- [x] 2.3 Add promotion apply endpoint with confirmation semantics, in-place role update, and party membership transition (verify: removed from `partyNPCs`, added to `partyMembers`).
- [x] 2.4 Ensure promotion apply does not auto-switch `active_character` (verify: active remains unchanged after successful apply).

## 3. GUI Manage Party Flow

- [x] 3.1 Add Add Existing source toggle (`Players`, `NPC Companions`, optional `All`) in `web/templates/partials/character_tabs.html` + `web/static/js/tabletop_mode.js` (verify: correct list load per mode).
- [x] 3.2 Add `Promote` action with confirm modal showing before/after role and warnings (verify: cancel does not modify data).
- [x] 3.3 Wire confirm action to promotion apply endpoint and refresh party tabs/state after success (verify: new PC tab appears, NPC entry removed).

## 4. Validation, Safety, and Logging

- [x] 4.1 Run shared post-transition audit/readiness checks and return warning context in apply response (verify: warnings visible in UI response handling).
- [x] 4.2 Add structured ASCII-safe logs for preview/apply outcomes (verify: logs include character name, action, success/failure).
- [x] 4.3 Ensure no promotion chat side effects are emitted (verify: no new chat lines generated during preview/apply).

## 5. Verification and Regression

- [x] 5.1 Compile checks for modified Python files (verify: `python3 -m py_compile <files>`).
- [x] 5.2 Functional smoke: promote one current NPC companion to PC without active-character switch (verify: party tracker state and UI tabs).
- [x] 5.3 Regression: existing Add Existing player flow and DM/roll-your-own creation flows remain functional.

## Session Verification Notes (2026-02-12)

- Promotion smoke verified with temporary NPC candidate (`Temp Promotion Smoke`):
  - `POST /api/party/promotion/preview` -> `200`, `success=true`
  - `POST /api/party/promotion/apply` -> `200`, `success=true`
  - Character moved from `partyNPCs` to `partyMembers`
  - `active_character` remained unchanged
  - Promoted file role markers became `player/player/player`
  - `character_id` generated and `_tabletop_role_history` appended
- Regression probes passed:
  - `/api/party/characters?source=players` returned candidates
  - `/api/party/characters?source=npc_companions` returned candidates
  - `POST /api/party/create_manual` with missing name returned expected `400`
  - `POST /api/party/create_player` with missing name returned expected `400`
- Test artifacts were cleaned up after run (temporary party entry + temporary character file removed).
