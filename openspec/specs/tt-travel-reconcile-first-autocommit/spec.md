# tt-travel-reconcile-first-autocommit Specification

## Purpose
TBD - created by archiving change travel-reconcile-first-autocommit. Update Purpose after archive.
## Requirements
### Requirement: Runtime SHALL auto-commit legal narrated travel on clear travel-intent turns
When a turn is classified as travel intent and the assistant narration clearly establishes legal movement that is compatible with current authoritative world truth, runtime SHALL reconcile and commit that travel state even if explicit `transitionLocation` is missing.

#### Scenario: Explicit narrated arrival without explicit transition action
- **WHEN** the turn is classified as travel intent
- **AND** the assistant narration clearly establishes arrival at one reachable destination
- **AND** no explicit `transitionLocation` action is present
- **THEN** runtime SHALL commit the destination as current location
- **AND** the turn SHALL NOT fail solely because the explicit travel action was omitted

### Requirement: Runtime SHALL preserve in-transit progress when travel is clear but arrival is not exact
When travel intent is clear but narration does not safely justify exact arrival at one destination, runtime SHALL preserve a soft in-transit/progress state rather than forcing a false exact destination or rejecting the turn.

#### Scenario: Travel progress toward known destination without exact arrival
- **WHEN** the turn is classified as travel intent
- **AND** the assistant narration clearly establishes movement toward a known reachable destination
- **AND** the narration does not clearly establish exact arrival
- **THEN** runtime SHALL persist in-transit or progress-toward state
- **AND** runtime SHALL NOT force an exact destination commit for that turn

### Requirement: Runtime SHALL fail closed on impossible travel and clarify unsafe ambiguity
Reconcile-first travel SHALL remain bounded by topology truth and safe destination resolution.

#### Scenario: Impossible travel remains blocking
- **WHEN** travel intent is clear
- **AND** the narrated destination or route is not legally reachable under current topology truth
- **THEN** runtime SHALL fail or block the travel commit
- **AND** runtime SHALL NOT auto-commit false location state

#### Scenario: Ambiguous destination does not auto-commit wrong canon
- **WHEN** travel intent is clear
- **AND** the narration could validly map to multiple destinations or progress interpretations
- **THEN** runtime SHALL preserve safe current truth or request clarification
- **AND** runtime SHALL NOT auto-commit one destination arbitrarily

### Requirement: Explicit travel actions SHALL remain fully supported
Reconcile-first travel SHALL be additive and SHALL preserve explicit `transitionLocation` as a preferred supported path.

#### Scenario: Explicit transition remains authoritative
- **WHEN** a response includes a valid explicit `transitionLocation`
- **THEN** runtime SHALL continue to process that explicit travel action normally
- **AND** reconcile-first inference SHALL NOT override it unnecessarily

