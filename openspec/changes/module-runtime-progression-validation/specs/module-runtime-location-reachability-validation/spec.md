## ADDED Requirements

### Requirement: Module validator SHALL enforce runtime room-graph reachability
The module validator SHALL validate intra-area room traversal using the same room connectivity contract consumed by runtime pathing, and SHALL fail when required room locations are unreachable in a playable module graph.

#### Scenario: Single-area module start room cannot reach a required room
- **WHEN** an area file defines room locations for a playable module
- **AND** the module start location exists
- **AND** one or more required room locations are unreachable from that start under `locations[*].connectivity`
- **THEN** validation SHALL fail with room IDs and file context

#### Scenario: Runtime connectivity pass accepts reachable room graph
- **WHEN** every required room location in the module is reachable from the module start under runtime room connectivity rules
- **THEN** the runtime room-graph validation SHALL pass

#### Scenario: Missing runtime connectivity is treated as a blocking error when traversal depends on it
- **WHEN** a module defines multiple room locations intended for traversal
- **AND** the runtime room graph lacks the explicit `connectivity` edges needed to traverse between them
- **THEN** validation SHALL fail rather than inferring traversal from map-only data

### Requirement: Runtime room-graph validation SHALL remain deterministic and fail closed only on explicit graph contradictions
The validator SHALL use explicit authored connectivity data only and SHALL NOT infer missing room links from narrative prose.

#### Scenario: Prose-only travel hint does not satisfy graph contract
- **WHEN** a room description implies a passage or tunnel in freeform text
- **AND** no explicit runtime room connectivity edge exists for that passage
- **THEN** validation SHALL treat the route as missing and SHALL fail if the route is required for progression
