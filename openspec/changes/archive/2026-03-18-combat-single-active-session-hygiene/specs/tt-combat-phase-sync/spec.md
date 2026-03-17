## MODIFIED Requirements

### Requirement: Phase and Prompt Contracts SHALL Remain Coherent

The combat phase value, required-response instructions, and turn-control behavior MUST not contradict each other within the same turn.

#### Scenario: Active encounter ownership remains stable after initiative lock
- **WHEN** a tabletop encounter has already accepted a valid `/init` and locked `initiativeWinner`
- **AND** subsequent player combat commands such as `/att` are processed
- **THEN** the runtime SHALL continue routing those commands to the same active encounter owner
- **AND** the system SHALL NOT regress to `Initiative pending` for a different duplicate encounter unless the owned encounter itself still requires `/init`
