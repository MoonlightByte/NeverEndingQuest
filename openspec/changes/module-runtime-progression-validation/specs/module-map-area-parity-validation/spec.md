## ADDED Requirements

### Requirement: Module validator SHALL reject room-graph parity drift between area and map files
The module validator SHALL compare `areas/*.json` room connectivity against the corresponding `map_*.json` room connections and SHALL fail when the two authored graphs disagree for the same room IDs.

#### Scenario: Map declares a room edge missing from area runtime connectivity
- **WHEN** a map file declares a connection between two room IDs
- **AND** the corresponding area file does not declare the same runtime room edge in `locations[*].connectivity`
- **THEN** validation SHALL fail with both file paths and the mismatched room IDs

#### Scenario: Area declares a runtime room edge missing from map file
- **WHEN** an area file declares a room edge in `locations[*].connectivity`
- **AND** the corresponding map file does not declare the same connection for the same room IDs
- **THEN** validation SHALL fail with both file paths and the mismatched room IDs

#### Scenario: Matching room graphs pass parity validation
- **WHEN** area connectivity and map connectivity describe the same room graph for a module area
- **THEN** the parity validation SHALL pass

### Requirement: Parity validation SHALL not mutate module content
Parity validation SHALL report authored drift and SHALL NOT auto-rewrite area files or map files during normal validator execution.

#### Scenario: Parity drift produces deterministic diagnostics only
- **WHEN** a map/area room-graph mismatch is detected
- **THEN** validation SHALL emit deterministic diagnostics
- **AND** SHALL NOT alter module JSON content as part of the validation run
