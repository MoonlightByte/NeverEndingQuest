## MODIFIED Requirements

### Requirement: Enemy phase batching SHALL include all valid living non-PC actors
Enemy-phase batch resolution SHALL deterministically include living enemy and DM-controlled NPC actors eligible for that phase.

#### Scenario: Enemy phase batch actor list
- **WHEN** enemy phase begins
- **THEN** the batch actor list includes all valid living non-PC actors for that phase
- **AND** excludes dead/defeated actors

### Requirement: PCs SHALL remain forbidden as DM-controlled actors and valid as targets
During enemy phase, PCs MUST remain forbidden as acting entities and SHALL remain valid targets for attacks, damage, and effects.

#### Scenario: Enemy damages non-active PC
- **WHEN** an enemy/NPC action targets a PC who is not the currently active PC
- **THEN** integrity validation accepts the update
- **AND** the corresponding character update action is processed normally

### Requirement: Integrity validation SHALL align with encounter plus multi-PC authoritative roster
Combatant integrity checks SHALL use authoritative combat rosters sufficient to validate legal target updates in multi-PC combat.

#### Scenario: Target not present in encounter creature subset but present in active multi-PC roster
- **WHEN** a legal target update references a PC from the active multi-PC roster
- **THEN** validation recognizes the target as legal
- **AND** does not reject the response as hallucinated actor usage
