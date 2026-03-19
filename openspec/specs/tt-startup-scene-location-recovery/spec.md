# tt-startup-scene-location-recovery Specification

## Purpose
TBD - created by archiving change tt-runtime-inventory-location-recovery. Update Purpose after archive.
## Requirements
### Requirement: Startup/history refresh SHALL recover canonical location from recent uniquely resolved scene evidence

When stale stored location conflicts with recent transcript evidence that uniquely places the party in one known active-module location, runtime SHALL repair canonical location before GUI/history rebuild rehydrates the stale location.

#### Scenario: Priest's Lodging recap overrides stale Ma's Watering Hole location on startup
- **GIVEN** `party_tracker.json` still records `NIG01`
- **AND** recent transcript or recap text clearly places the party in `NIG04 Priest's Lodging`
- **AND** no newer explicit location action re-establishes `NIG01`
- **WHEN** startup/history location recovery runs before conversation-history refresh
- **THEN** runtime SHALL commit `NIG04` as the canonical current location
- **AND** the GUI/top bar/history rebuild SHALL read `NIG04` instead of `NIG01`

### Requirement: Startup scene-location recovery SHALL use conservative active-module aliases

Recent scene evidence SHALL be matched using conservative canonical aliases derived from active-module location metadata.

#### Scenario: Natural room-title prose matches a canonical room-labeled location
- **GIVEN** runtime knows `NIG04` as `Room 4: Priest's Lodging`
- **AND** active-module metadata includes `source_room_title` of `Priest's Lodging`
- **WHEN** recent transcript says `the priest's lodging`
- **THEN** startup scene-location recovery SHALL treat that as valid evidence for `NIG04`

### Requirement: Ambiguous or weak startup scene evidence SHALL fail open

Startup/history recovery SHALL NOT rewrite canonical location when recent transcript evidence is not uniquely resolvable.

#### Scenario: Multiple candidate rooms or vague destination prose
- **WHEN** recent transcript evidence could refer to more than one known location or only suggests travel progress without clear arrival
- **THEN** startup/history recovery SHALL NOT rewrite canonical current location

