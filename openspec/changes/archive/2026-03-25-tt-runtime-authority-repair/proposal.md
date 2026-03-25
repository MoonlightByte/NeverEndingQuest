## Why

Runtime combat coherence improved, but the next Win11 test exposed a broader authority split outside combat: party location can remain stuck on an older room, hidden authored NPCs like Father Aldric can be treated as present by validation but still fail movement resolution, and `updatePlot` can emit unsupported status values like `resolved` that trigger retry loops instead of converging state. This needs fixing now because these contradictions block live module progression even when the narration itself is already correct.

## What Changes

- MUST add deterministic runtime reconciliation that can commit current location from unique same-turn scene or plot evidence when explicit location actions are missing.
- MUST normalize unsupported plot status aliases (for example `resolved`) to schema-safe canonical values before validation and persistence.
- MUST extend `moveBackgroundNPC` lookup so hidden or revealable authored NPC identities can be resolved through the same canonical fallback path as visible NPCs.
- MUST preserve fail-closed behavior for ambiguous NPC identity and ambiguous location evidence.
- SHOULD emit explicit normalization and reconciliation logs so future operator debugging can distinguish canonicalization from new authored state.
- Non-goals:
  - MUST NOT widen location commits to vague travel-progress prose.
  - MUST NOT silently add party membership for background NPCs.
  - MUST NOT change plot schema enums or broaden them beyond the existing canonical set.

## Capabilities

### New Capabilities
- `tt-plot-status-enum-normalization`: Canonicalize plot status aliases to the schema-supported enum set before persistence.
- `tt-scene-plot-location-reconciliation`: Reconcile canonical current location from unique same-turn plot or scene evidence when narration/state drift leaves location stale.

### Modified Capabilities
- `tt-npc-move-hint-fallback`: Extend strict-first/fallback NPC movement lookup to include hidden or revealable authored NPC identities, not just visible location NPC records.

## Impact

- Affected code: `main.py`, `utils/travel_state_sync_guard.py`, `core/ai/action_handler.py`, `updates/plot_update.py`, and targeted regression suites around scene sync and NPC lookup.
- Merge safety: host-file edits remain minimal and SHOULD stay limited to existing TABLETOP MODE reconciliation hooks.
- SP/MP compatibility: behavior MUST remain backward compatible; deterministic normalization and location repair apply safely in both modes.
- Rollout risk: false-positive location commits are the main risk, so reconciliation MUST require one unique resolvable target and MUST fail open otherwise.
- Fallback strategy: if reconciliation cannot prove one canonical target, runtime SHALL keep current behavior and only log degraded/no-op outcomes.