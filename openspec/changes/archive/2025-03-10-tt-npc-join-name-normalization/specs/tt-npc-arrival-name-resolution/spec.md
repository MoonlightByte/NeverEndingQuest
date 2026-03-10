## ADDED Requirements

### Requirement: Action-name alias handling SHALL match mention alias handling

Alias resolution for action payload names SHALL be consistent with alias resolution used for narration mentions in arrival-sync evaluation.

#### Scenario: Short mention and short action name resolve to same canonical identity
- **WHEN** narration references short NPC alias `Kira`
- **AND** action payload also uses short alias `Kira`
- **AND** canonical resolver maps both unambiguously to `Scout Kira`
- **THEN** arrival-sync evaluation SHALL treat both as the same canonical NPC identity

#### Scenario: Mention resolves but action alias is ambiguous
- **WHEN** narration mention resolves unambiguously
- **AND** action payload alias maps to multiple candidates
- **THEN** arrival-sync evaluation SHALL fail closed for ambiguous action identity
- **AND** SHALL require explicit disambiguated canonical action name

### Requirement: Canonical identity checks SHALL be action-type invariant

Canonical identity matching SHALL behave consistently across `updatePartyNPCs` add and `moveBackgroundNPC` action paths.

#### Scenario: updatePartyNPCs canonical parity
- **WHEN** `updatePartyNPCs` adds an NPC using a short alias
- **THEN** canonical identity match SHALL use the same resolver semantics as mention parsing

#### Scenario: moveBackgroundNPC canonical parity
- **WHEN** `moveBackgroundNPC` provides `npcName` using a short alias
- **THEN** canonical identity match SHALL use the same resolver semantics as mention parsing
