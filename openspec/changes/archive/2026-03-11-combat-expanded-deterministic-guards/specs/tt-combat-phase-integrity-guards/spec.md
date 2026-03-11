## ADDED Requirements

### Requirement: Combat deterministic guards SHALL reject explicit phase-integrity contradictions when authoritative phase state makes them unambiguous
Combat deterministic guards SHALL reject explicit phase-integrity contradictions when authoritative combat phase, turn, and hostile-state data makes the contradiction unambiguous.

#### Scenario: Forbidden phase actor attempts an illegal action
- **WHEN** a combat response assigns an action to an actor forbidden by the current combat phase
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Enemy batch stops before the next legal PC boundary
- **WHEN** combat is in an enemy batch
- **AND** hostiles remain to be processed before the next legal PC boundary
- **AND** the response stops or prompts prematurely
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Combat exits while hostiles remain
- **WHEN** a combat response issues exit or equivalent combat-end behavior
- **AND** living hostiles still remain in the encounter
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

#### Scenario: Round increments before all required PCs acted
- **WHEN** a combat response increments the round counter
- **AND** authoritative phase state shows not all required PC turns for the round are complete
- **THEN** deterministic combat validation SHALL reject the response before probabilistic validation

### Requirement: Combat phase-integrity guards SHALL fail open on non-authoritative ambiguity
Combat phase-integrity guards SHALL defer to the existing validation path when authoritative state is unavailable or contradictory.

#### Scenario: Missing or inconsistent phase state defers to existing validation path
- **WHEN** authoritative combat phase or queue state is unavailable or inconsistent
- **THEN** deterministic combat validation SHALL NOT reject solely from inferred phase assumptions
