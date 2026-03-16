# tt-travel-intent-state-sync-guard Specification

## Purpose
TBD - created by archiving change tt-travel-intent-state-sync-guard. Update Purpose after archive.
## Requirements
### Requirement: Clear travel-intent turns SHALL not accept narration-only arrival without location state sync
When the player clearly expresses travel intent, the runtime SHALL reject a response that narrates arrival, entry, emergence, or traversal into a new location unless the action bundle includes a matching `transitionLocation` state change.

#### Scenario: Travel narration reaches a new location without transition action
- **WHEN** the user utterance is classified as travel intent
- **AND** the assistant response explicitly narrates the party reaching or entering a new location
- **AND** the response omits `transitionLocation`
- **THEN** runtime validation SHALL reject the response before acceptance

#### Scenario: Valid travel response commits state
- **WHEN** the user utterance is classified as travel intent
- **AND** the assistant response narrates movement to a new location
- **AND** the action bundle includes `transitionLocation`
- **THEN** the travel state-sync guard SHALL pass

### Requirement: Travel-intent turns SHALL remain action-free only when the response keeps the party at the current location
A travel-intent response SHALL be allowed to omit `transitionLocation` only when it explicitly blocks, aborts, or defers movement while keeping the party grounded at the current location.

#### Scenario: Current-location blocker response remains valid without transition
- **WHEN** the user utterance is classified as travel intent
- **AND** the assistant response explicitly states that movement is blocked from the current location
- **AND** the response does not narrate arrival at a different location
- **THEN** runtime validation SHALL allow the response without `transitionLocation`

#### Scenario: Clarification response remains valid without transition
- **WHEN** the user utterance is classified as travel intent
- **AND** the assistant response asks the player to choose or clarify a route before travel completes
- **AND** the response does not narrate arrival at a different location
- **THEN** runtime validation SHALL allow the response without `transitionLocation`

### Requirement: Travel-intent responses SHALL reject explicit contradictory mixed-location narration
The runtime SHALL reject a travel-intent response that explicitly narrates conflicting location outcomes within the same response when no valid action-state transition explains both locations.

#### Scenario: Response narrates destination arrival and snap-back to current location
- **WHEN** the user utterance is classified as travel intent
- **AND** the assistant response explicitly narrates arrival in a destination scene
- **AND** the same response explicitly re-grounds the party in a different current-location scene without state actions explaining both
- **THEN** runtime validation SHALL reject the response as contradictory travel-state narration

### Requirement: Travel-state sync guard SHALL fail open on ambiguous prose
The travel-state sync guard SHALL defer to existing validation when the narration is too ambiguous to determine whether the party actually arrived elsewhere.

#### Scenario: Ambiguous atmospheric language does not trigger deterministic rejection
- **WHEN** the user utterance is classified as travel intent
- **AND** the response contains travel-adjacent atmosphere but no explicit arrival or destination commitment
- **THEN** the travel-state sync guard SHALL NOT reject on that basis alone

