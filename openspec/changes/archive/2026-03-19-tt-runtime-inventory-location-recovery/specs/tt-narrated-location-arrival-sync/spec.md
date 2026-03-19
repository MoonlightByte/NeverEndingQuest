## ADDED Requirements

### Requirement: Narrated arrival reconciliation SHALL support conservative room-title aliases

Narrated-location-arrival reconciliation SHALL support conservative aliases derived from canonical room metadata so natural room-title prose can still commit the correct location.

#### Scenario: Room prefix is omitted in arrival narration
- **GIVEN** runtime knows `NIG04` as `Room 4: Priest's Lodging`
- **AND** the narration says the party steps into `the priest's lodging`
- **AND** no explicit `transitionLocation` or explicit `updatePartyTracker.currentLocationId` is present
- **WHEN** narrated-location-arrival reconciliation runs
- **THEN** runtime SHALL treat that room-title alias as valid evidence for `NIG04`

#### Scenario: Alias collision remains uncommitted
- **WHEN** the same stripped room-title alias could resolve to more than one known location
- **THEN** narrated-location-arrival reconciliation SHALL fail open and SHALL NOT commit location
