## MODIFIED Requirements

### Requirement: Transition Travel Bundles MUST Pair Location and Time
Narrative movement responses SHALL result in both travel-state commitment and time advancement in the same effective commit cycle. This SHALL apply both to explicit `transitionLocation` bundles and to legal travel state committed by runtime reconciliation.

#### Scenario: Valid explicit travel bundle
- **WHEN** the model narrates party movement to a new location
- **AND** actions include `transitionLocation` and `updateTime`
- **THEN** runtime SHALL apply both the location commit and the provided time advancement
- **AND** `updateTime.timeEstimate` SHALL be an integer minute value

#### Scenario: Inferred arrival commit without explicit updateTime
- **WHEN** runtime reconciles a legal narrated arrival without explicit `updateTime`
- **THEN** runtime SHALL apply deterministic time advancement in the same effective commit cycle
- **AND** travel time SHALL remain synchronized with the committed location state

#### Scenario: In-transit progress commit without explicit updateTime
- **WHEN** runtime commits legal in-transit or progress-toward travel state
- **AND** no explicit `updateTime` action is present
- **THEN** runtime SHALL apply deterministic time advancement for that progress commit

### Requirement: Runtime SHALL Fail-Open with Deterministic Auto-Time
If travel state is committed without explicit time advancement, runtime SHALL preserve continuity by applying deterministic fallback minutes.

#### Scenario: Explicit same-area transition without updateTime
- **WHEN** actions include `transitionLocation` and no `updateTime`
- **AND** effective transition remains within same area
- **THEN** runtime SHALL apply one synthetic `updateTime` of `10` minutes
- **AND** runtime SHALL log `STATE_SYNC` indicating fallback application

#### Scenario: Explicit cross-area transition without updateTime
- **WHEN** actions include `transitionLocation` and no `updateTime`
- **AND** transition crosses area boundary
- **THEN** runtime SHALL apply one synthetic `updateTime` of `20` minutes
- **AND** runtime SHALL log `STATE_SYNC` indicating fallback application

#### Scenario: Inferred arrival commit uses deterministic travel time
- **WHEN** runtime commits a legal narrated arrival through reconcile-first travel handling
- **AND** no explicit `updateTime` action exists
- **THEN** runtime SHALL apply deterministic fallback travel time appropriate to the effective transition
- **AND** runtime SHALL keep clock state synchronized with the committed arrival

#### Scenario: In-transit progress commit uses deterministic travel time
- **WHEN** runtime commits legal in-transit or progress-toward travel state
- **AND** no explicit `updateTime` action exists
- **THEN** runtime SHALL apply deterministic fallback travel time appropriate to that progress step

#### Scenario: Explicit updateTime remains authoritative
- **WHEN** actions already include `updateTime`
- **THEN** runtime SHALL NOT inject additional synthetic `updateTime`
- **AND** existing explicit time behavior SHALL remain unchanged

#### Scenario: Non-travel turns are unchanged
- **WHEN** the turn does not result in explicit or inferred travel-state commitment
- **THEN** runtime SHALL NOT inject synthetic `updateTime`
