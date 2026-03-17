## ADDED Requirements

### Requirement: Web input SHALL block during idle waits instead of synthesizing blank turns

When the web runtime is waiting for player input, it SHALL wait for real queued input and SHALL NOT generate synthetic empty-input turns that re-enter gameplay processing.

#### Scenario: No pending web input
- **GIVEN** the web game loop is running
- **AND** the input queue has no user message available yet
- **WHEN** the runtime waits for input
- **THEN** it SHALL remain blocked on input acquisition
- **AND** it SHALL NOT return a synthetic blank line to the main loop

#### Scenario: Real user input arrives after idle wait
- **GIVEN** the runtime has been blocked waiting for web input
- **WHEN** a real user message is enqueued
- **THEN** the input layer SHALL return that message to the main loop unchanged
- **AND** normal turn processing SHALL continue

### Requirement: Idle blocking SHALL preserve gameplay stability

Removing synthetic blank turns SHALL NOT break existing status signaling or queue-based gameplay recovery behavior.

#### Scenario: Idle wait with status signaling
- **WHEN** the runtime updates input status while still waiting for a real message
- **THEN** gameplay SHALL remain stable
- **AND** no synthetic idle turn SHALL be emitted
