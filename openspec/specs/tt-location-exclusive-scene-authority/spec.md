# tt-location-exclusive-scene-authority Specification

## Purpose
TBD - created by archiving change tt-narrator-location-exclusivity-guards. Update Purpose after archive.
## Requirements
### Requirement: Narrator present-scene claims SHALL respect authoritative location
The narrator response contract SHALL reject present-scene instantiation of location-exclusive content when the authoritative current location does not match the exclusive content's required location.

#### Scenario: NC01 cannot instantiate NC05 confrontation scene
- **WHEN** authoritative location is `NC01`
- **AND** narrator output presents Malarok as physically present at ritual altar/Voidstone confrontation
- **THEN** validation SHALL fail closed with correction guidance

#### Scenario: NC01 may foreshadow NC05 threats
- **WHEN** authoritative location is `NC01`
- **AND** narrator output references distant ritual pressure or future confrontation without present-scene instantiation
- **THEN** validation SHALL allow narration

### Requirement: Exclusivity violations SHALL use correction loop
Location-exclusivity contradictions SHALL be surfaced through existing retry/correction flow rather than silently accepted.

#### Scenario: Contradiction triggers retry guidance
- **WHEN** exclusivity violation is detected
- **THEN** response SHALL include concise correction guidance
- **AND** narrator generation SHALL retry under the same authoritative location context

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

