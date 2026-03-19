# tt-authoritative-same-module-transition Specification

## Purpose
TBD - created by archiving change tt-authoritative-transition-inventory-runtime-reset. Update Purpose after archive.
## Requirements
### Requirement: Same-module transition validation SHALL use fresh authoritative topology
Same-module `transitionLocation` requests SHALL be validated against a fresh authoritative topology snapshot derived from current module area data rather than a stale cached runtime graph.

#### Scenario: Valid same-module edge succeeds
- **WHEN** the party is at `NIG04`
- **AND** the current module area data declares `NIG05` in `NIG04` connectivity
- **AND** the assistant emits `transitionLocation(newLocation="NIG05")`
- **THEN** runtime SHALL accept the transition as a valid same-module move

#### Scenario: Stale cached graph does not override valid fresh topology
- **WHEN** a cached graph view disagrees with the current module area file about a same-module local edge
- **AND** fresh area topology confirms the edge is valid
- **THEN** runtime SHALL use the fresh topology result for same-module transition validation

### Requirement: Same-module transition execution SHALL commit canonical location state before narration depends on it
For same-module movement, runtime SHALL commit canonical location state successfully before any downstream arrival or scene narration is treated as authoritative history.

#### Scenario: Successful same-module move commits tracker state
- **WHEN** a same-module `transitionLocation` request is validated successfully
- **THEN** runtime SHALL update canonical party location state to the destination before any arrival-dependent scene context is generated

#### Scenario: Failed same-module move leaves canonical location unchanged
- **WHEN** a same-module `transitionLocation` request fails validation or execution
- **THEN** runtime SHALL preserve the prior canonical location state unchanged

