## ADDED Requirements

### Requirement: Plot or encounter evidence SHALL reconcile one canonical current location when explicit location actions are absent
When a response advances one uniquely resolvable plot point or references one uniquely resolvable encounter location and omits explicit location state updates, runtime SHALL infer the matching canonical location for the active module.

#### Scenario: Cellar hallway plot update repairs stale priest-lodging location
- **GIVEN** `party_tracker.json` still records `NIG04`
- **AND** the same response includes `updatePlot` for `PP005`
- **AND** `PP005` resolves to `NIG05`
- **AND** no explicit `transitionLocation` or `updatePartyTracker.currentLocationId` action exists
- **WHEN** deterministic location reconciliation runs
- **THEN** runtime SHALL inject `updatePartyTracker` for `NIG05`

#### Scenario: Ritual encounter repairs stale cellar location
- **GIVEN** `party_tracker.json` still records `NIG04`
- **AND** the same response includes `updateEncounter` for `NIG06-E1`
- **AND** no explicit `transitionLocation` or `updatePartyTracker.currentLocationId` action exists
- **WHEN** deterministic location reconciliation runs
- **THEN** runtime SHALL inject `updatePartyTracker` for `NIG06`

### Requirement: Explicit location actions SHALL remain authoritative over plot reconciliation
Plot-driven reconciliation SHALL be additive and SHALL not duplicate or override an explicit location commit already present in the response.

#### Scenario: Explicit transition already present
- **WHEN** the response already includes `transitionLocation` or `updatePartyTracker.currentLocationId`
- **THEN** plot-driven location reconciliation SHALL inject no additional location action

### Requirement: Ambiguous or multi-target plot evidence SHALL fail open
Runtime SHALL not rewrite current location from plot evidence unless one safe canonical target is provable.

#### Scenario: Multiple updated plot points in different locations
- **WHEN** a response updates plot points that resolve to different canonical locations
- **THEN** runtime SHALL inject no inferred location commit

#### Scenario: Unknown plot point location mapping
- **WHEN** `updatePlot.plotPointId` cannot be resolved to one known active-module location
- **THEN** runtime SHALL inject no inferred location commit
- **AND** SHALL preserve existing location state
