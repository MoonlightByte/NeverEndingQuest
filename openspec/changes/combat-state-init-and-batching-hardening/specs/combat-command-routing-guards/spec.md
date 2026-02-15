## ADDED Requirements

### Requirement: Combat-only slash commands SHALL be blocked outside active combat
The narrative loop SHALL reject combat-only slash commands when no active combat encounter is present.

#### Scenario: `/init` used outside active combat
- **WHEN** a user sends `/init <roll>` with no active encounter
- **THEN** the command is intercepted before narrator generation
- **AND** the user receives deterministic system guidance

#### Scenario: `/end` used outside active combat
- **WHEN** a user sends `/end` with no active encounter
- **THEN** the command is intercepted before narrator generation
- **AND** no exit/farewell narration is generated from combat command intent

### Requirement: Guarded command handling SHALL be deterministic
Guarded command responses SHALL use consistent, non-LLM system messaging.

#### Scenario: Repeated guarded command usage
- **WHEN** a guarded combat-only command is used multiple times outside combat
- **THEN** each response is deterministic and does not depend on narrator variation
