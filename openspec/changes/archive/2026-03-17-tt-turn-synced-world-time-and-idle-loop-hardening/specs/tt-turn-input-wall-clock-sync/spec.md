## ADDED Requirements

### Requirement: Accepted non-empty turns SHALL advance world time by bounded elapsed real minutes

The runtime SHALL bridge real table discussion time into world time by applying elapsed whole real minutes when a non-empty player turn is accepted.

#### Scenario: First accepted turn seeds timestamp only
- **GIVEN** no prior valid wall-clock marker is stored
- **WHEN** the runtime accepts the first non-empty player turn
- **THEN** it SHALL persist a wall-clock marker
- **AND** it SHALL NOT advance world time for that seeding turn

#### Scenario: Later turn advances by elapsed whole minutes
- **GIVEN** a valid prior wall-clock marker is stored
- **AND** six real minutes have elapsed since the previous accepted turn
- **WHEN** the runtime accepts the next non-empty player turn
- **THEN** world time SHALL advance by `6` minutes
- **AND** the stored wall-clock marker SHALL update to the new accepted-turn timestamp

#### Scenario: Sub-minute gap does not change world time
- **GIVEN** a valid prior wall-clock marker is stored
- **AND** less than one full real minute has elapsed
- **WHEN** the next non-empty player turn is accepted
- **THEN** runtime SHALL update the stored wall-clock marker
- **AND** world time SHALL remain unchanged

### Requirement: Wall-clock advancement SHALL be clamped and fail-open

The runtime SHALL prevent runaway time jumps and SHALL recover safely from malformed persisted metadata.

#### Scenario: Large real gap is clamped
- **GIVEN** a valid prior wall-clock marker is stored
- **AND** elapsed real minutes exceed the configured per-turn maximum
- **WHEN** the next non-empty player turn is accepted
- **THEN** world time SHALL advance by the configured maximum only
- **AND** runtime SHALL remain playable

#### Scenario: Malformed stored timestamp resets safely
- **GIVEN** the persisted wall-clock marker is missing, malformed, or unparseable
- **WHEN** the runtime attempts turn-synced wall-clock application
- **THEN** it SHALL reset the marker to the current accepted-turn timestamp
- **AND** it SHALL NOT raise a gameplay-blocking error
- **AND** it SHALL NOT advance world time for that reset turn

### Requirement: Empty or synthetic turns SHALL NOT trigger wall-clock advancement

Turn-synced wall-clock behavior SHALL apply only to accepted non-empty player turns.

#### Scenario: Idle wait without a real turn
- **WHEN** the runtime remains idle waiting for player input
- **THEN** it SHALL NOT apply wall-clock time advancement
