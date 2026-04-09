# tt-scene-entity-violence-resolution Specification

## Purpose
TBD - created by archiving change scene-entity-combat-validity-contract. Update Purpose after archive.
## Requirements
### Requirement: Incorporeal scene entities SHALL resolve physical attacks as no-effect scene interactions
When a scene entity is marked incorporeal and scene-only, physical weapon attacks against that entity SHALL resolve as a no-effect scene interaction rather than entering formal combat.

#### Scenario: Sword passes through incorporeal projection
- **GIVEN** a current-scene entity has `sceneEntity.manifestation="incorporeal"`
- **AND** `sceneEntity.violencePolicy="incorporeal_no_effect"`
- **WHEN** a player declares a physical attack against that entity
- **THEN** runtime SHALL NOT start combat solely from that attack
- **AND** SHALL NOT apply HP or status harm to the entity
- **AND** narration MAY describe the attack passing through, dispersing, or failing to connect materially

### Requirement: Corporeal scene entities SHALL support helpless-kill-else-escalate policy when authored
When a corporeal scene entity opts into the selected default violence policy, runtime SHALL resolve helpless harm deterministically and SHALL otherwise escalate through explicit combat data.

#### Scenario: Helpless corporeal scene entity is killed without formal combat
- **GIVEN** a current-scene entity has `sceneEntity.manifestation="corporeal"`
- **AND** `sceneEntity.violencePolicy="helpless_kill_else_escalate"`
- **AND** the entity is narratively helpless or nonresisting
- **WHEN** a player declares lethal violence against that entity
- **THEN** runtime MAY resolve the harm without formal combat
- **AND** SHALL persist the resulting scene-state change deterministically

#### Scenario: Resisting corporeal scene entity escalates through combat proxy
- **GIVEN** a current-scene entity has `sceneEntity.manifestation="corporeal"`
- **AND** `sceneEntity.violencePolicy="helpless_kill_else_escalate"`
- **AND** the entity is resisting, defended, or the outcome is tactically contested
- **AND** the entity declares a `combatProxy`
- **WHEN** a player declares violence against that entity
- **THEN** runtime SHALL require formal combat escalation through that proxy
- **AND** SHALL NOT treat the raw scene-entity label as a monster statblock identity

### Requirement: Escalation without required proxy SHALL fail closed with explicit guidance
If a scene entity requires combat escalation but lacks its required combat proxy, runtime SHALL fail closed with operator-visible feedback.

#### Scenario: Corporeal escalation requested without proxy
- **GIVEN** a current-scene entity has `sceneEntity.combatValidity="escalatable"`
- **AND** violence resolution requires formal combat
- **AND** no valid `combatProxy` is authored
- **WHEN** runtime attempts to escalate
- **THEN** action processing SHALL return an explicit error
- **AND** SHALL explain that the entity is escalatable scene content missing required combat proxy data
- **AND** SHALL NOT emit misleading combat-start narration

