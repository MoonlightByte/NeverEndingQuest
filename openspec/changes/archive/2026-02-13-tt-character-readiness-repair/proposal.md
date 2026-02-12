## Why

Character sheet readiness warnings currently identify incomplete narrative fields but do not provide an in-UI recovery path. In live tabletop sessions this creates friction because facilitators must manually edit JSON files or run scripts to restore sheet completeness.

## What Changes

- Add a `Repair` action in the character sheet readiness warning UI.
- Implement a preview-and-confirm repair flow that proposes narrative-field fixes before save.
- Add a backend readiness-repair endpoint that runs outside chat and can synthesize missing narrative fields from character state and recent context.
- Enforce strict writable-field whitelist so repair can only update approved narrative fields.
- Re-run shared character readiness audit after proposal and after apply; block apply if audit still fails.
- Add repair cooldown/rate-limiting and logging for safety and observability.
- Keep legacy behavior intact when repair is not invoked.

Explicit non-goals:
- No direct edits to mechanical fields (HP, AC, abilities, saves, slots, equipment mechanics).
- No changes to combat state machines or encounter logic.
- No chat-visible narration output for repair operations.

## Capabilities

### New Capabilities
- `tt-character-readiness-repair`: GUI-initiated, preview-confirm repair workflow for readiness warnings with backend-safe field constraints and audit gating.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `web/templates/game_interface.html` (Repair button + preview modal wiring)
  - `web/routes/character_sheet_routes.py` (repair preview/apply endpoints)
  - `utils/character_creation_audit.py` (repair-safe helpers/shared constraints)
  - optional helper module for bounded LLM prompt build and response sanitization
- APIs/endpoints:
  - New endpoints for readiness repair preview and apply (non-chat path).
- Dependencies/systems:
  - Reuse existing audit pipeline; optional LLM usage via existing client factory.
- Rollout risk: medium (touches GUI + write path), mitigated by preview-confirm UX, whitelist enforcement, and audit-before-save gate.
- Fallback strategy:
  - If LLM generation fails, return deterministic template fallback proposal for missing narrative fields.
  - If apply validation fails, keep original character unchanged and return actionable errors.
- Merge-safety/SP-MP compatibility:
  - Additive TABLETOP MODE hooks only; single-player flow remains unaffected unless repair UI is used.
