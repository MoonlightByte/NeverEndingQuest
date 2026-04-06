## Why

NeverEndingQuest currently conflates visible scene presence with combat validity: an authored location NPC can appear in narration and the UI, yet fail hard if the narrator tries to attack or formalize that same entity as a monster. This becomes a cross-module narrative blocker for emissaries, apparitions, diplomats, and other scene actors who need to be present in play without automatically becoming combat statblocks.

## What Changes

- Add an additive scene-entity contract for authored location NPCs so visibility, manifestation, and combat validity are tracked separately from monster authorization.
- Add a reusable violence-resolution contract for scene entities, including incorporeal no-effect resolution and the selected default policy for corporeal non-combatants: helpless kill, else escalate.
- Add a createEncounter guard that MUST reject non-combat-valid scene entities with a specific failure class instead of surfacing a generic unauthorized-monster error.
- Preserve existing fail-closed monster authorization for real enemies while allowing authored cross-module hooks like Red (The Crimson Binder) to remain visible and narratable as non-combatant presences.
- Keep the change additive and opt-in so unannotated modules continue to behave as they do today.

Non-goals:
- a full generic NPC combat system for every location NPC
- broad encounter-schema redesign
- replacing existing monster authority or hydration flows
- auto-generating combat stats for every villager, diplomat, or shopkeeper
- removing human-DM freedom to allow cruelty, intimidation, or massacre scenarios in live play

Rollout risk and fallback:
- MUST keep the new scene-entity metadata optional and backward compatible with existing location NPC records.
- MUST preserve current monster authorization and hydration boundaries for real combat enemies.
- MUST fail closed with explicit surfaced errors when escalation is requested for a scene entity that lacks required combat proxy data.
- SHOULD keep first-pass rollout narrow: Red in `Night_of_the_Restless_Dead` is the proving case, while the contract remains reusable for later modules.
- SHOULD prefer explicit operator-visible diagnostics over silent narrator redirects when combat-validity rules block escalation.

Merge-safety and compatibility:
- MUST keep host-file edits minimal and marked with `# TABLETOP MODE:` comments.
- MUST preserve single-player and tabletop mode compatibility.
- MUST avoid widening combat for unannotated location NPCs.
- SHOULD keep module authoring additive by extending existing location `npcs[]` records instead of requiring a second parallel scene roster.

## Capabilities

### New Capabilities
- `tt-scene-entity-presence-combat-validity`: authored location NPCs can declare scene-only or escalatable presence without being implicitly combat-valid.
- `tt-scene-entity-violence-resolution`: scene entities resolve player violence according to manifestation and explicit policy, including incorporeal no-effect and helpless-kill-else-escalate behavior.

### Modified Capabilities
- `tt-createencounter-failure-surfacing`: createEncounter failures must distinguish non-combat-valid scene entities from generic unauthorized monster references.

## Impact

- Affected code: `core/ai/action_handler.py`, `core/generators/combat_builder.py`, monster authorization helpers, pre-combat scene helpers, and likely a new shared scene-entity helper under `utils/`.
- Affected data contracts: `schemas/loca_schema.json` and authored module area JSON NPC records.
- Affected prompts: system prompt combat commitment guidance and likely validation wording for scene-only versus escalatable entities.
- Affected tests: createEncounter failure surfacing, scene-entity violence resolution, and targeted module regressions for `Night_of_the_Restless_Dead`.
- Systems impacted: scene presence, combat initiation, module authoring semantics, and DM-facing runtime diagnostics.
- Provider/quota behavior: no new provider dependency is introduced; the change SHOULD reduce wasted full-model retries by surfacing deterministic scene-entity routing failures earlier.
