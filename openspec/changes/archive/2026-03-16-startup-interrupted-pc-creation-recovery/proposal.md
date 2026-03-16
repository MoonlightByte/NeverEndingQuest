## Why

Startup multi-PC onboarding can be interrupted after the first player character is persisted, which leaves `party_tracker.json` looking complete enough to skip the startup wizard on the next launch. In that partial state, tabletop party-management UI can disappear and normal chat requests to create another PC can fall into invalid `updatePartyNPCs` retries instead of returning to a safe creation flow.

## What Changes

- Preserve immediate first-PC persistence during startup, but add a resumable startup-incomplete contract so interrupted onboarding MUST return to the startup wizard on next launch instead of dropping into gameplay.
- Keep tabletop party-management access visible in one-PC bootstrap states when tabletop mode is intended, so the facilitator MUST retain a deterministic `Manage Party` entry even before a second PC exists.
- Add a deterministic runtime guard for brand-new PC creation requests during normal gameplay chat so the system MUST route facilitators to dedicated creation flows (or explicit system guidance) instead of misusing `updatePartyNPCs` with novel names.
- Add focused regression coverage for interrupted startup recovery, one-PC tabletop UI availability, and new-PC request fail-closed behavior.

### MUST Contract

- MUST treat interrupted startup onboarding as incomplete until the startup loop reaches explicit completion.
- MUST preserve already-created PCs when startup is resumed after interruption.
- MUST keep the tabletop `Manage Party` entry available when tabletop mode is enabled or startup onboarding is incomplete.
- MUST NOT allow arbitrary gameplay narration to create a brand-new player character through `updatePartyNPCs`.
- MUST preserve backward compatibility for normal single-player startup and existing dedicated creation endpoints.

### SHOULD Guidance

- SHOULD keep startup recovery state in lightweight persisted metadata that existing party tracker consumers ignore safely.
- SHOULD prefer deterministic system guidance over speculative LLM repair when a facilitator asks for a new PC during normal gameplay chat.
- SHOULD keep host-file edits minimal and marked with `# TABLETOP MODE:` comments where applicable.

### Non-goals

- No redesign of the startup interview content or character-sheet schema.
- No conversion of arbitrary gameplay chat into a full freeform player-character creation workflow.
- No changes to combat, encounter, or unrelated narrator validation systems beyond the new-PC creation guard.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `tt-pc-creation-workflows`: extend startup onboarding requirements to cover interrupted-startup resume behavior, one-PC tabletop party-management access, and safe routing for new player-character creation requests outside dedicated creation mode.

## Impact

- Affected code (planned):
  - `utils/startup_wizard.py`
  - `web/web_interface.py`
  - `web/templates/game_interface.html`
  - `web/templates/partials/character_tabs.html`
  - `main.py`
  - `config_template.py`
  - focused regression tests under `scripts/`
- Merge-safety impact: low to medium; changes stay within existing startup and tabletop extension boundaries.
- SP/MP compatibility impact:
  - Single-player startup MUST remain unchanged when onboarding finishes normally.
  - Tabletop bootstrap MUST recover safely from interrupted one-PC states.
- Rollout risk: medium; startup gating and UI visibility changes can strand facilitators if the resume contract is incomplete.
- Fallback strategy:
  - If startup completion state is ambiguous, prefer resuming startup instead of auto-entering gameplay.
  - If runtime new-PC creation intent cannot be routed safely, emit explicit system guidance and avoid party-state mutation.
