## ADDED Requirements

### Requirement: Runtime SHALL reconcile explicit narrated arrival into one known location

When narration clearly places the party at one uniquely resolved known location in the active module, runtime SHALL commit that party location even if `transitionLocation` was omitted.

#### Scenario: Hermit's Refuge narrated arrival commits party location
- **GIVEN** the party is currently recorded at `RO01`
- **AND** runtime knows `TW04` as `Hermit's Refuge`
- **AND** narration explicitly places the party in Maelo's clearing or lodge scene
- **AND** no explicit `transitionLocation` or `updatePartyTracker.currentLocationId` is present
- **WHEN** narrated-location-arrival reconciliation runs
- **THEN** runtime SHALL infer a location commit to `TW04`
- **AND** later UI/location refresh SHALL read the corrected party location

### Requirement: Explicit location actions SHALL remain authoritative

Narrated-arrival reconciliation SHALL be additive and SHALL NOT duplicate existing explicit location actions.

#### Scenario: Explicit transition already present
- **WHEN** the response already includes a valid `transitionLocation` or explicit `updatePartyTracker.currentLocationId`
- **THEN** runtime SHALL not inject a second inferred location commit

### Requirement: Ambiguous or progress-only narration SHALL fail open

Runtime SHALL avoid committing party location when narration does not justify one unique arrival destination.

#### Scenario: Progress-only narration remains uncommitted
- **WHEN** narration says the refuge is ahead or nearby but does not place the party there yet
- **THEN** narrated-arrival reconciliation SHALL NOT commit party location

#### Scenario: Multiple possible destinations remain uncommitted
- **WHEN** narration could resolve to more than one known location
- **THEN** narrated-arrival reconciliation SHALL NOT commit party location
