## ADDED Requirements

### Requirement: Spatial remediation SHALL classify fixed-point adjacency contradictions

Spatial remediation MUST stop and classify unresolved connected-room adjacency contradictions when repeated planning produces no further change.

#### Scenario: Connected rooms remain non-cardinal after remediation
- **GIVEN** strict spatial validation reports two directly connected rooms whose coordinates are not cardinally adjacent
- **AND** a subsequent remediation pass produces no coordinate or direction delta
- **WHEN** convergence evaluation runs
- **THEN** the workflow SHALL classify the result as residual spatial contradiction debt
- **AND** SHALL NOT continue retrying unchanged spatial blockers

### Requirement: Shared planner SHALL be reused for convergence repair

Spatial convergence repair SHALL reuse the shared planner rather than introducing a parallel coordinate fixer.

#### Scenario: Convergence repair reruns spatial planning
- **GIVEN** a module area/map pair with strict spatial contradictions
- **WHEN** deterministic convergence repair executes
- **THEN** it SHALL reuse the shared spatial planner and authored connectivity as the source of truth
- **AND** any rewritten coordinates and directions SHALL remain mutually consistent under strict validation
