## Why

After campaign reset + startup creation, two failures were observed in tabletop web flow:

1. Character Sheet stalls on `Loading character stats...` after first PC creation, then updates later mid-narrative.
2. Startup does not reliably continue multi-PC onboarding; it falls through to gameplay with only one PC.

Root causes identified:
- Startup additional-PC prompt uses inline `input("... (y/n): ")` without newline emission, so web output capture may not surface the question reliably.
- Web input timeout can inject blank input that is treated as implicit "no", exiting the add-more loop.
- Character sheet renderer reads `data.name` before null guard, causing JS exceptions when early stats responses return null during startup race.

## What Changes

- Harden startup add-more flow in `utils/startup_wizard.py`:
  - Emit newline-visible prompt text before input collection.
  - Require explicit `y/yes` or `n/no` responses.
  - Reprompt on blank/invalid input (no implicit default to "no").
  - Proceed to gameplay only after explicit negative confirmation.
- Harden character sheet stats rendering in `web/templates/game_interface.html`:
  - Enforce null-safe guard before any `data.*` access.
  - Render deterministic waiting/error states when stats are temporarily unavailable.
  - Keep periodic refresh behavior and ensure later valid stats render without manual reload.

### MUST Contract

- MUST reprompt for additional PC creation until explicit `y/yes` or `n/no` is provided.
- MUST NOT treat blank/timeout input as implicit `no`.
- MUST keep startup-to-gameplay transition blocked until explicit loop exit decision is made.
- MUST keep character sheet stats rendering null-safe (no JS exception on null data).
- MUST preserve merge-safe TABLETOP MODE style and existing SP compatibility boundaries.

### SHOULD Guidance

- SHOULD keep startup prompt copy concise and facilitator-friendly for in-person tabletop use.
- SHOULD surface backend `error` text in stats panel when available.
- SHOULD keep host-file edits minimal and tagged with `# TABLETOP MODE:` where applicable.

### Non-goals

- No redesign of startup wizard interview content.
- No rewrite of socket transport architecture.
- No changes to character schema or party tracker schema.
- No combat/narration behavior changes beyond startup gating.

## Capabilities

### New Capabilities

- `tt-character-sheet-stats-loading-resilience`

### Modified Capabilities

- `tt-pc-creation-workflows`

## Impact

- Affected code (planned):
  - `utils/startup_wizard.py`
  - `web/templates/game_interface.html`
  - `scripts/test_startup_multipc_reprompt.py` (new)
  - `scripts/test_character_sheet_stats_resilience.py` (new or equivalent source-contract tests)
- Rollout risk: Low to medium (startup loop behavior + UI null-guard).
- Fallback strategy:
  - If startup reprompt logic fails, do not auto-advance; show explicit retry messaging.
  - If stats fetch is unavailable, keep waiting/error render and allow periodic retry path to recover.
