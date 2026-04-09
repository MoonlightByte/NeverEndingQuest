## ADDED Requirements

### Requirement: Existing authored-exit grounding surfaces SHALL remain valid
Route-block grounding SHALL continue to accept deterministic state/action support and current authored metadata surfaces such as `connectivity`, `transition_hints`, and already-recognized blocker-like keys.

#### Scenario: Existing transition hints still ground route logic
- **GIVEN** a location already uses `transition_hints` or existing blocker-like metadata
- **WHEN** authored-exit grounding is evaluated
- **THEN** runtime SHALL preserve those existing surfaces as valid grounding inputs

### Requirement: Scene-authority widening SHALL NOT require a broad new blocker ontology
This change SHALL not introduce a large new blocker metadata language unless current low-risk surfaces are proven insufficient.

#### Scenario: Route-blocking remains stable during metadata-first exclusivity migration
- **WHEN** metadata-first scene-authority checks are introduced
- **THEN** authored-exit grounding SHALL continue to work without requiring immediate module-wide blocker metadata rewrites

### Requirement: Missing new scene-authority metadata SHALL NOT break exit grounding
Exit-grounding validation SHALL remain independent of whether a location has adopted the new scene-authority metadata.

#### Scenario: Legacy module still uses exit grounding without sceneAuthority
- **GIVEN** a legacy location has no `sceneAuthority` metadata
- **WHEN** narrator output claims an adjacent exit is blocked
- **THEN** runtime SHALL continue evaluating authored-exit grounding using existing deterministic and authored surfaces
