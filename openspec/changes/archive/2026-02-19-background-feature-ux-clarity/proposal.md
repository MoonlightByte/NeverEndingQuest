## Why

Players are unsure how to fill `backgroundFeature.name` and `backgroundFeature.description` in the portrait profile modal, and legacy placeholder values like `Feature` and `Standard background feature` leak into character sheets, PDF exports, and portrait prompts. We should improve guided input UX and remove ambiguous defaults so character narrative fields are clearer and more useful.

## What Changes

- Add guided UX copy for background feature fields in Character Sheet and portrait profile flows, including concrete examples and concise writing guidance.
- Add deterministic defaulting/suggestion behavior so blank or generic background-feature values can be replaced with useful SRD-style or generic narrative text.
- Add placeholder-remediation behavior for legacy character files containing generic background feature values.
- Extend readiness/profile audits to detect generic placeholder values (not only empty strings) and surface actionable warnings.
- Add non-blocking migration tooling/reporting so existing campaigns can be normalized safely.

### Non-Goals

- **MUST NOT** change combat mechanics, initiative logic, save/restore contracts, or other mechanical character state.
- **MUST NOT** introduce hard-fail validation that blocks gameplay for legacy characters during this UX-focused pass.
- **SHOULD NOT** force a strict canonical phrase set that removes DM/player narrative customization.

## Capabilities

### New Capabilities
- `background-feature-guided-entry-ux`: Guided field labels, examples, and helper text for `backgroundFeature.name` and `backgroundFeature.description` in profile/create flows.
- `background-feature-placeholder-remediation`: Detection and cleanup path for legacy generic background-feature placeholders with safe fallback behavior.

### Modified Capabilities
- `character-sheet-completeness-audit`: Extend completeness/readiness detection to treat generic placeholder strings as incomplete narrative quality for background feature fields.
- `tt-character-readiness-repair`: Expand repair suggestions/patch scope to optionally include `backgroundFeature.name` alongside description when values are generic placeholders.

## Impact

- Affected UI: `web/templates/game_interface.html`, `web/templates/partials/character_tabs.html`.
- Affected backend logic: `utils/character_creation_audit.py`, `web/web_interface.py`, `web/routes/tabletop_party_routes.py`, and potentially helper scripts for migration/backfill.
- Data impact: Character JSON narrative fields only (`backgroundFeature.name`, `backgroundFeature.description`) with no mechanical-state mutation.
- Merge safety:
  - **MUST** keep host-file edits minimal and marked `# TABLETOP MODE:` where required.
  - **SHOULD** prefer helper/extension logic and additive checks over broad structural rewrites.
- SP/MP compatibility:
  - **MUST** preserve single-player and tabletop mode behavior; changes are narrative UX/data-quality improvements only.
- Rollout risk and fallback:
  - Risk: over-aggressive replacement could override intentional custom text.
  - **MUST** gate remediation to clearly generic placeholder patterns only.
  - **MUST** fail open (log warning, preserve original data) if remediation tooling errors.
  - **SHOULD** provide dry-run/report mode before applying bulk updates.
