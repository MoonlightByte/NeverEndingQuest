## MODIFIED Requirements

### Requirement: Transition Travel Bundles MUST Pair Location and Time

Narrative movement responses SHALL result in both travel-state commitment and time advancement in the same effective commit cycle. This SHALL apply both to explicit `transitionLocation` bundles and to legal travel state committed by runtime reconciliation.

#### Scenario: Inferred arrival commit without explicit updateTime
- **WHEN** runtime reconciles a legal narrated arrival without explicit `updateTime`
- **THEN** runtime SHALL apply deterministic time advancement in the same effective commit cycle
- **AND** travel time SHALL remain synchronized with the committed location state
- **AND** inferred action ordering SHALL keep time advancement paired with the arrival commit

### Requirement: Runtime SHALL Fail-Open with Deterministic Auto-Time

If travel state is committed without explicit time advancement, runtime SHALL preserve continuity by applying deterministic fallback minutes.

#### Scenario: Inferred arrival commit uses deterministic travel time
- **WHEN** runtime commits a legal narrated arrival through reconcile-first travel handling
- **AND** no explicit `updateTime` action exists
- **THEN** runtime SHALL apply deterministic fallback travel time appropriate to the effective transition
- **AND** runtime SHALL keep clock state synchronized with the committed arrival

#### Scenario: Explicit updateTime remains authoritative
- **WHEN** actions already include explicit `updateTime`
- **THEN** runtime SHALL NOT inject additional synthetic `updateTime`
- **AND** existing explicit time behavior SHALL remain unchanged
