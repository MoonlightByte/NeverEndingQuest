## MODIFIED Requirements

### Requirement: Runtime SHALL auto-commit legal narrated travel on clear travel-intent turns
When a turn is classified as travel intent and the assistant narration clearly establishes legal movement that is compatible with current authoritative world truth, runtime SHALL reconcile and commit that travel state even if explicit `transitionLocation` is missing.

#### Scenario: Explicit narrated arrival without explicit transition action
- **WHEN** the turn is classified as travel intent
- **AND** the assistant narration clearly establishes arrival at one reachable destination
- **AND** no explicit `transitionLocation` action is present
- **THEN** runtime SHALL commit the destination as current location
- **AND** the turn SHALL NOT fail solely because the explicit travel action was omitted

#### Scenario: Implicit same-module sublocation descent commits one adjacent authored target
- **WHEN** the turn is classified as travel intent
- **AND** the assistant narration and/or player utterance clearly establish descent or entry from the current room into one uniquely resolvable adjacent authored sublocation
- **AND** no explicit `transitionLocation` or explicit `updatePartyTracker.currentLocationId` action is present
- **THEN** runtime SHALL commit that adjacent authored destination as current location
- **AND** runtime SHALL NOT require the destination name to appear verbatim if the local scene evidence is still uniquely resolvable
