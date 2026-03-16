## MODIFIED Requirements

### Requirement: Retry correction context SHALL be bounded

Retry correction text SHALL not be generated for failures whose only invalidation source is an already-reconciled authoritative domain.

#### Scenario: Reconciled travel-only complaint produces no retry correction
- **GIVEN** deterministic runtime already reconciled travel state sync successfully
- **AND** the LLM validator complains only about travel action plumbing
- **WHEN** retry handling evaluates the failure
- **THEN** runtime SHALL suppress that complaint
- **AND** SHALL NOT generate retry correction text for that domain

#### Scenario: Reconciled NPC-only complaint produces no retry correction
- **GIVEN** deterministic runtime already reconciled NPC scene presence successfully
- **AND** the LLM validator complains only about NPC arrival movement plumbing
- **WHEN** retry handling evaluates the failure
- **THEN** runtime SHALL suppress that complaint
- **AND** SHALL NOT generate retry correction text for that domain

#### Scenario: Mixed-domain failure still generates bounded correction
- **GIVEN** an LLM failure includes both reconciled-domain complaints and unreconciled failures
- **WHEN** retry handling evaluates the result
- **THEN** correction text SHALL reference only the unreconciled failure
- **AND** SHALL exclude already-reconciled domain complaints
