## Context

The current runtime has three separate concepts but only two mechanical lanes:

- location `npcs[]` provide visible scene actors and roleplay presences
- location `monsters[]` and module monster authority provide combat-valid enemy candidates
- encounter files persist only `player`, `npc`, and `enemy` combatants

That split works for classic fights, but it fails for cross-module emissaries and scene actors like Red (The Crimson Binder). Red is authored as a current-location NPC and must remain visible for narrative continuity, yet formal combat fail-closes because the runtime only knows how to turn `createEncounter.monsters[]` into authorized monster statblocks. The result is a contradiction: the DM can narrate Red, but Python cannot classify Red as either a monster or a safe non-combatant presence.

Constraints:
- Python state remains ground truth for violence, targeting, and combat entry.
- Existing monster authority and encounter schema must remain stable.
- Module JSON changes must stay additive and schema-valid.
- Host-file edits must stay minimal and marked `# TABLETOP MODE:`.
- First rollout should solve the Crimson Binder problem without accidentally widening every authored NPC into a combat target.

## Goals / Non-Goals

**Goals:**
- Add an additive scene-entity contract that separates visibility from combat validity.
- Preserve scene-only entities in authored module data and runtime scene presence.
- Provide a deterministic violence-resolution policy for scene entities.
- Surface explicit errors when the narrator tries to force a scene-only entity into `createEncounter`.
- Support the chosen default policy for corporeal non-combatants: helpless kill, else escalate.
- Keep unannotated module content on its existing behavior path.

**Non-Goals:**
- Building a universal social combat or crime/justice system.
- Replacing monster authority with generic NPC stat synthesis.
- Making every authored location NPC automatically attackable.
- Creating a parallel full encounter schema for civilians.
- Solving every future alignment/morality consequence system in this change.

## Decisions

### Decision: Extend existing location NPC records with additive `sceneEntity` metadata
Scene-only and escalatable actors SHALL stay inside location `npcs[]` and SHALL gain an optional additive `sceneEntity` object instead of moving to a separate `sceneEntities[]` collection.

Proposed shape:

```json
"sceneEntity": {
  "combatValidity": "scene_only|escalatable",
  "manifestation": "corporeal|incorporeal",
  "violencePolicy": "incorporeal_no_effect|helpless_kill_else_escalate",
  "combatProxy": "Commoner|Cultist|Guard|..."
}
```

Rationale:
- authored NPC visibility already flows from location `npcs[]`
- the UI and scene lookup path already consume `npcs[]`
- additive metadata is merge-safe and avoids duplicate identities

Alternatives considered:
- new sibling `sceneEntities[]` list: rejected because it duplicates current scene-actor surfaces and increases authoring drift risk
- overloading location `monsters[]`: rejected because those are encounter seeds, not general scene actors

### Decision: Separate manifestation from social role
The contract SHALL treat `apparition`/`projection` as a physical manifestation concern, not as a social role. A diplomat, peasant, enforcer, emissary, or shopkeeper may all be corporeal or incorporeal, but violence resolution depends on manifestation plus policy, not on narrative title alone.

Rationale:
- "diplomat" does not answer whether a sword passes through the target
- Red needs to stay present as a Pumpkin King representative while remaining non-combat-valid
- the runtime needs a mechanical distinction, not just flavor labels

Alternatives considered:
- role-only taxonomy (`diplomat`, `shopkeeper`, `apparition`): rejected because it mixes social identity and mechanics

### Decision: First-pass violence resolution remains bounded and opt-in
Violence against scene entities SHALL resolve through two first-pass paths only:

- `incorporeal_no_effect`: physical attacks do not create combat, do not apply harm, and should narrate pass-through/no-effect behavior
- `helpless_kill_else_escalate`: if the entity is helpless or nonresisting, runtime may resolve deterministic removal/status change without formal combat; otherwise runtime MUST require escalation through an explicit `combatProxy`

If escalation is required but `combatProxy` is absent, the system SHALL fail closed with explicit feedback.

Rationale:
- preserves Python authority without needing generic stats for every NPC
- allows evil-PC harm scenarios without pretending every villager is a monster file
- keeps initial scope narrow and auditable

Alternatives considered:
- always escalate any violence to combat: rejected because it over-mechanizes helpless scene harm and forces stat proxies for every case
- allow harm only for pre-authored full combatants: rejected because it blocks desired cruelty/civilian violence scenarios entirely

### Decision: Combat guard should run before monster authorization hard-fail messaging
`createEncounter` processing SHALL detect when a requested monster label resolves to a current-scene authored NPC with `sceneEntity` metadata and SHALL surface a scene-entity-specific error before generic unauthorized-monster messaging is used.

Rationale:
- prevents misleading diagnostics like "missing monster" when the entity is actually authored scene content
- keeps the monster authority contract intact for real enemies

Alternatives considered:
- leave the current unauthorized-monster path unchanged: rejected because it obscures the design distinction users need to understand

### Decision: Red is the proving-case annotation, not the universal default
The first implementation SHALL annotate Red in `Night_of_the_Restless_Dead` as an incorporeal, scene-only entity. Unannotated NPCs SHALL preserve their existing behavior until a module author opts them into the new contract.

Rationale:
- keeps rollout safe
- proves the hook without widening every legacy location NPC
- allows later modules to opt into corporeal escalation case-by-case

Alternatives considered:
- infer scene-entity metadata heuristically from descriptions or names: rejected as too fragile for authoritative mechanics

## Risks / Trade-offs

- [Metadata sprawl in area JSON] -> Keep `sceneEntity` optional, small, and schema-bounded.
- [Narrator still emits invalid `createEncounter` payloads] -> Add explicit prompt guidance and deterministic pre-builder guard with clear surfaced errors.
- [Corporeal escalation path stalls because proxy missing] -> Fail closed with explicit guidance and tests; require explicit proxy for opt-in escalatable entities in first pass.
- [Opt-in model leaves some legacy NPCs non-harmable] -> Accept as a rollout trade-off; future modules can annotate entities deliberately rather than widening semantics globally.
- [UI confusion between visible and attackable] -> Preserve current scene visibility while surfacing better runtime feedback; optional client metadata can be added later if needed.
- [Red remains narratively present but mechanically untouchable] -> This is intentional for the projection case and should be encoded, not improvised.

## Migration Plan

1. Extend `schemas/loca_schema.json` to allow optional `sceneEntity` metadata on location NPC objects.
2. Add a shared runtime helper (new `utils/scene_entity_contract.py`) for lookup and policy evaluation.
3. Add createEncounter preflight/guard logic that distinguishes scene-only/escalatable entities from monster authorization failures.
4. Add bounded violence-resolution handling for scene entities, reusing existing background-NPC mutation paths where deterministic non-combat harm is allowed.
5. Update prompts/validation guidance so the LLM treats scene-only entities as visible presences rather than automatic monsters.
6. Annotate Red in `Night_of_the_Restless_Dead` as the proving-case scene-only incorporeal entity.
7. Add targeted regressions and validate the change.

Rollback strategy:
- `sceneEntity` metadata is additive and can be ignored safely if runtime hooks are removed.
- Prompt guidance can be reverted independently of data annotations.
- Guard logic can be removed without schema rollback because additive fields do not break legacy readers.

## Open Questions

- Whether the client should surface additive `sceneEntity` debugging metadata in party/scene payloads or remain runtime-only for now.
- Whether later phases should introduce a bounded generic proxy catalog for escalatable scene entities that omit `combatProxy`, or keep explicit proxies mandatory.
- Whether magical but harmful non-combat presences (for example, curse auras or remote projections that can still inflict effects) need a later third violence policy beyond this first pass.
