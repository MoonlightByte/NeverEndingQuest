## ADDED Requirements

### Requirement: Transition Travel Bundles MUST Pair Location and Time
Narrative movement responses SHALL include both location transition and time advancement in the same action bundle.

#### Scenario: Valid travel bundle
- **WHEN** the model narrates party movement to a new location
- **THEN** actions SHALL include `transitionLocation` and `updateTime` together
- **AND** `updateTime.timeEstimate` SHALL be an integer minute value

#### Scenario: Validator flags missing travel time
- **WHEN** a response includes `transitionLocation` without `updateTime`
- **THEN** validation guidance SHALL mark the response as incomplete travel-state sync
- **AND** correction guidance SHALL request adding `updateTime`

### Requirement: Runtime SHALL Fail-Open with Deterministic Auto-Time
If movement arrives without explicit time advancement, runtime SHALL preserve continuity by applying deterministic fallback minutes.

#### Scenario: Same-area transition without updateTime
- **WHEN** actions include `transitionLocation` and no `updateTime`
- **AND** effective transition remains within same area
- **THEN** runtime SHALL apply one synthetic `updateTime` of `10` minutes
- **AND** runtime SHALL log `STATE_SYNC` indicating fallback application

#### Scenario: Cross-area transition without updateTime
- **WHEN** actions include `transitionLocation` and no `updateTime`
- **AND** transition crosses area boundary
- **THEN** runtime SHALL apply one synthetic `updateTime` of `20` minutes
- **AND** runtime SHALL log `STATE_SYNC` indicating fallback application

#### Scenario: Explicit updateTime remains authoritative
- **WHEN** actions already include `updateTime`
- **THEN** runtime SHALL NOT inject additional synthetic `updateTime`
- **AND** existing action behavior SHALL remain unchanged

#### Scenario: Non-transition turns are unchanged
- **WHEN** actions do not include `transitionLocation`
- **THEN** runtime SHALL NOT inject synthetic `updateTime`
