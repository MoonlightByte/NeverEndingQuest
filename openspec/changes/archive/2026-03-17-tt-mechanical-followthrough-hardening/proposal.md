## Why

Recent narrator/validator hardening improved pace, freedom, and umpire-style direct answers, but the session transcript shows persistent follow-through gaps where narration advances mechanical reality faster than JSON state and pre-combat UI surfaces do. Explicitly narrated gifts, consumable use, class-feature depletion, and hostile scene presence can all drift from canonical runtime state, which undermines player trust even when the narration itself feels excellent.

## What Changes

- Add a narrow but generic reconcile-first path for explicit narrated scene gifts and item grants so clearly assigned rewards become canonical inventory updates instead of remaining narration-only state; runtime MUST avoid module- or NPC-specific hardwires.
- Extend the structured `updateCharacterInfo.ops` contract with canonical flat-op enforcement, legacy nested-op normalization, and deterministic class-feature usage updates for resources such as Rage.
- Align validator/combat truth packs and DM Note mechanical summaries with the live character schema (`equipment`, `ammunition`, nested `classFeatures[].usage`) so narrator and validator surfaces can actually see the same reality Python persists.
- Add pre-combat hostile scene presence to the top-strip payload so current-location hostiles such as the Naiad or Captain Gorvek appear before formal encounter creation.
- Add focused regression coverage for narrated item grants, malformed-op normalization, feature-usage depletion, truth-pack schema parity, and pre-combat hostile rendering.
- SHOULD tighten action-prediction observability so routing/debug logs inspect raw player input instead of DM-note-augmented world-state blobs.

## Capabilities

### New Capabilities
- `tt-scene-item-grant-reconcile`: deterministic reconcile-first handling for explicit narrated scene gifts and item grants.
- `tt-pre-combat-hostile-scene-presence`: pre-combat UI payload and rendering for current-location hostile scene actors.
- `tt-dm-note-mechanical-visibility`: DM Note mechanical summaries sourced from the live character schema for inventory and limited-use resources.

### Modified Capabilities
- `tt-structured-character-ops-contract`: broaden the ops contract to require canonical flat op records, compatibility normalization for legacy nested shapes, and first-class class-feature usage ops.
- `tt-validator-mechanical-truth-pack`: require touched-character truth packs to surface nested feature-usage and live-schema inventory data.
- `tt-combat-validator-mechanical-truth-pack`: require combat truth packs to surface nested feature-usage and live-schema inventory data for touched PCs/allied NPCs.

## Impact

- Affected code: `main.py`, `updates/update_character_info.py`, `utils/validator_truth_pack.py`, `utils/multi_pc_dm_note.py`, `core/managers/combat_manager.py`, `web/extensions/tabletop_socket_handlers.py`, `web/templates/game_interface.html`, and targeted regression scripts under `scripts/`.
- Affected systems: narrator/runtime reconciliation, character update deterministic ops, validator truth surfaces, combat truth surfaces, DM Note prompt context, and pre-combat tabletop UI scene visibility.
- Merge-safety impact: moderate; host-file edits stay narrow and MUST remain marked with `# TABLETOP MODE:` comments.
- SP/MP compatibility impact: MUST preserve single-player behavior; multiplayer/tabletop paths gain additional deterministic follow-through without changing baseline single-player contracts.
- Risk: medium; touches narration-to-state reconciliation and UI presence surfaces, so ambiguity guards and regression locks are required.
- Fallback: if any deterministic reconcile slice proves unsafe, runtime SHALL preserve current explicit-action behavior and degrade to narration-only handling rather than inventing ambiguous state.
