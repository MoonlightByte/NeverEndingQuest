## ADDED Requirements

### Requirement: Module validator SHALL enforce graph-valid plot progression locations
The module validator SHALL verify that the module starting location, `plotPoints[*].location`, and explicit branch metadata paths are reachable under the authored runtime room graph.

#### Scenario: Plot point location is unreachable from module start
- **WHEN** a plot point declares a `location`
- **AND** the module starting location exists
- **AND** the plot point location is unreachable from the module start under the runtime room graph
- **THEN** validation SHALL fail with the plot point ID and unreachable location ID

#### Scenario: Explicit branch path contains a broken step
- **WHEN** branch metadata declares an explicit `path` array or `bypass` array of room IDs
- **AND** one or more consecutive steps in that path are not connected under the authored runtime room graph
- **THEN** validation SHALL fail with the branch identifier and the broken step pair

#### Scenario: Reachable plot progression passes
- **WHEN** plot point locations and explicit branch paths are reachable under the authored runtime room graph
- **THEN** plot progression path validation SHALL pass

### Requirement: Finale or conclusion progression SHALL remain gated by explicit upstream progression state
The module validator SHALL fail when a finale or conclusion beat is graph-valid but lacks explicit prerequisite or progression gating where the authored plot sequence otherwise indicates a downstream dependency.

#### Scenario: Conclusion beat lacks explicit prerequisite gate
- **WHEN** a module plot declares a downstream finale or conclusion plot point
- **AND** upstream plot points define a progression chain leading into that finale
- **AND** the finale lacks an explicit prerequisite or equivalent gating field linking it to its upstream dependency
- **THEN** validation SHALL fail with the finale plot point ID and the missing-gate reason
