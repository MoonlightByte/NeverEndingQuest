## ADDED Requirements

### Requirement: Runtime SHALL reconcile implicit same-module sublocation descent when one adjacent authored target is uniquely provable
When scene evidence clearly establishes descent or entry from the current canonical room into one uniquely resolvable adjacent authored sublocation, runtime SHALL commit canonical location state even if the assistant omitted explicit `transitionLocation` and explicit `updatePartyTracker.currentLocationId`.

#### Scenario: Cathedral crevice descent commits Cathedral Storage
- **WHEN** the canonical current location is `NIG02`
- **AND** `NIG03` is an authored adjacent destination from `NIG02`
- **AND** player and assistant scene text clearly establish descent through the altar crevice into the catacombs below
- **AND** no explicit `transitionLocation` or explicit `updatePartyTracker.currentLocationId` is present
- **THEN** runtime SHALL infer and commit canonical location state to `NIG03`

### Requirement: Inferred sublocation commit SHALL remain narrow and fail open on ambiguity
Implicit sublocation descent reconciliation SHALL only commit canonical location when one adjacent authored target is uniquely provable from safe local evidence.

#### Scenario: Multiple possible lower-depth targets do not auto-commit
- **WHEN** the scene evidence could map to more than one adjacent or downstream authored sublocation
- **THEN** runtime SHALL inject no inferred location commit

#### Scenario: Progress-only lower-depth tension does not auto-commit
- **WHEN** the scene prose only establishes approach, tension, or foreshadowing toward deeper space without clear entry into one authored room
- **THEN** runtime SHALL inject no inferred location commit

### Requirement: Direct DM adjudication for location drift SHALL remain supported
The system SHALL continue to support direct DM adjudication responses when players ask why canonical location truth drifted from narrated scene truth.

#### Scenario: Player asks why the party restarted upstairs
- **WHEN** a player directly asks the DM to explain or resolve a location mismatch
- **THEN** runtime SHALL allow a valid adjudication-first response without forcing an automatic location commit on that question alone
