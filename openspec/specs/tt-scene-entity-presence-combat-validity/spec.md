# tt-scene-entity-presence-combat-validity Specification

## Purpose
TBD - created by archiving change scene-entity-combat-validity-contract. Update Purpose after archive.
## Requirements
### Requirement: Authored scene entities SHALL separate visible presence from combat validity
An authored location NPC MAY declare additive `sceneEntity` metadata, and runtime SHALL treat that metadata as a separate contract from monster authorization so the actor can remain visibly present in the scene without being implicitly valid for formal combat generation.

#### Scenario: Scene-only entity remains visible after location load
- **GIVEN** a current-location NPC includes `sceneEntity.combatValidity="scene_only"`
- **WHEN** the scene is loaded for narration or UI payload generation
- **THEN** the entity SHALL remain available as a visible authored scene actor
- **AND** runtime SHALL NOT infer that the entity is a combat-valid monster solely from that presence

#### Scenario: Unannotated location NPC preserves legacy behavior
- **WHEN** a location NPC has no `sceneEntity` metadata
- **THEN** existing location-NPC behavior SHALL remain unchanged
- **AND** the new contract SHALL NOT widen that NPC into a combat-valid target automatically

### Requirement: Scene-only entities SHALL be blocked from formal encounter enemy generation
Runtime SHALL reject scene-only entities from `createEncounter.monsters[]` inputs.

#### Scenario: Narrator targets scene-only apparition as monster
- **GIVEN** a current-location NPC includes `sceneEntity.combatValidity="scene_only"`
- **AND** the narrator emits `createEncounter` using that entity in `monsters[]`
- **THEN** runtime SHALL reject encounter creation before monster hydration
- **AND** SHALL classify the failure as a non-combat-valid scene-entity error
- **AND** SHALL NOT misclassify the entity as a missing or unauthorized monster statblock only

### Requirement: Escalatable scene entities SHALL declare explicit escalation data
If a scene entity may escalate from scene presence into formal combat, the authored entity SHALL provide explicit bounded escalation metadata.

#### Scenario: Escalatable envoy declares combat proxy
- **GIVEN** a location NPC includes `sceneEntity.combatValidity="escalatable"`
- **THEN** the entity SHALL declare a violence policy
- **AND** SHALL declare a `combatProxy` when its escalation path can enter formal combat

### Requirement: Scene-only illusion content SHALL stay outside structured combatant requirements
Builder, finisher, and publication flows MUST preserve the distinction between scene-only illusion content and combat-valid entities so scene-only illusions do not trigger monster hydration or media blockers unless they are explicitly authored as combat-valid.

#### Scenario: Scene-only illusion modeled as scene entity avoids monster-readiness blocking
- **WHEN** authored illusion or mindscape content is represented through `sceneEntity` metadata instead of structured monster fields
- **THEN** monster hydration and gameplay media gates MUST NOT require monster statblocks or monster media for that content

#### Scenario: Structured monster fields remain strict for combat-valid entities
- **WHEN** authored content appears in `locations[].monsters[]` or other combat-valid structured fields
- **THEN** build and publication flows MUST continue to require full combat-valid hydration and media support
- **AND** MUST NOT treat the content as scene-only by implication

