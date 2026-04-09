## ADDED Requirements

### Requirement: Runtime SHALL prefer authored scene-authority metadata when available
Location-exclusive present-scene evaluation SHALL use authored `sceneAuthority.presentSceneAnchors` metadata when relevant anchors are present.

#### Scenario: Metadata-present anchor is evaluated without module-specific registry
- **GIVEN** runtime is evaluating narration for a module with authored scene-authority metadata
- **AND** the narration references an authored anchor alias
- **THEN** validation SHALL use the authored anchor ownership/location truth to evaluate present-scene correctness

### Requirement: Foreshadowing SHALL remain allowed
Scene-authority widening SHALL preserve the two-lane contract between foreshadowing and present-scene instantiation.

#### Scenario: Metadata-present anchor is foreshadowed but not instantiated
- **GIVEN** narration references an authored anchor as a distant or future threat
- **AND** the narration does not instantiate that anchor as present in the current scene
- **THEN** validation SHALL allow the narration

### Requirement: Legacy fallback SHALL remain during migration
If authored scene-authority metadata is absent, runtime SHALL preserve current fallback behavior rather than fail open or require immediate project-wide remediation.

#### Scenario: Thornwood legacy fallback remains active
- **GIVEN** authored scene-authority metadata is absent or incomplete for a guarded location pair
- **WHEN** runtime evaluates narrator output
- **THEN** the existing Thornwood fallback guard SHALL remain available during migration
- **AND** behavior for the currently protected contradiction class SHALL remain intact
