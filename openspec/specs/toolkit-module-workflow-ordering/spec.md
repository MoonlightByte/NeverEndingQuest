# toolkit-module-workflow-ordering Specification

## Purpose
TBD - created by archiving change gui-builder-module-workflow-ui-ordering. Update Purpose after archive.
## Requirements
### Requirement: Toolkit UI SHALL prioritize module-builder workflow ordering
Toolkit module tooling SHALL present module-authoring workflow surfaces before graphic-pack tooling while preserving access to existing manager tools.

#### Scenario: Module builder path is visually first
- **GIVEN** the module toolkit UI is rendered
- **WHEN** the author views the top-level workflow tabs or grouped surfaces
- **THEN** `Generate Module` and `Generate Module Media` SHALL appear before graphic-pack tooling
- **AND** `Module Media Generator` SHALL remain easy to find as the post-build media path

#### Scenario: Graphic pack tools remain available
- **GIVEN** the toolkit UI has been reordered
- **WHEN** the author navigates to graphic-pack tooling
- **THEN** monster and NPC manager tools SHALL still be present and functional
- **AND** the reordering SHALL NOT remove those surfaces

