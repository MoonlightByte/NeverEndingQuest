## ADDED Requirements

### Requirement: Plot status aliases SHALL normalize to canonical schema values
Runtime plot updates SHALL convert supported alias statuses into the canonical plot-schema enum before validation or persistence.

#### Scenario: Resolved canonicalizes to completed
- **WHEN** an `updatePlot` action or downstream plot update payload uses `resolved`
- **THEN** runtime SHALL normalize that value to `completed`
- **AND** plot persistence SHALL validate against the existing schema without retrying on the alias alone

#### Scenario: Case and spacing variants canonicalize safely
- **WHEN** a plot update uses a supported alias variant such as `Completed`, `in_progress`, or `not_started`
- **THEN** runtime SHALL normalize the status to the canonical stored enum value

### Requirement: Unknown plot statuses SHALL remain fail-safe
Runtime SHALL not silently invent new durable plot status values outside the canonical enum set.

#### Scenario: Unsupported alias remains blocked
- **WHEN** a plot update uses an unknown status that is not part of the supported alias map
- **THEN** runtime SHALL fail validation or return a clear error path
- **AND** the stored plot data SHALL remain unchanged

### Requirement: Canonical plot enum vocabulary SHALL remain unchanged
Normalization SHALL preserve one canonical durable vocabulary for plot state.

#### Scenario: Schema remains canonical
- **WHEN** normalized plot data is saved to `module_plot.json`
- **THEN** stored `status` values SHALL remain limited to `not started`, `in progress`, and `completed`
