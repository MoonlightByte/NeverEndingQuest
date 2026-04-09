# tt-authored-exit-grounding Specification

## Purpose
TBD - created by archiving change tt-narrator-location-exclusivity-guards. Update Purpose after archive.
## Requirements
### Requirement: Route-blocking narration SHALL be grounded in authoritative state or authored blockers
Narrator claims that an authored adjacent route is blocked SHALL require deterministic support from committed state/actions or authored blocker metadata.

#### Scenario: Unsupported blockade claim is rejected
- **WHEN** authoritative location has authored adjacent exits (for example `NC01 -> NC02/NC03`)
- **AND** narrator claims those exits are blocked without deterministic support
- **THEN** validation SHALL fail closed with correction guidance

#### Scenario: Supported blockade claim is accepted
- **WHEN** narrator route-blocking claim is supported by committed deterministic state/action or authored blocker metadata
- **THEN** validation SHALL allow the claim

### Requirement: Guard SHALL not block valid travel progression
Route-block grounding checks SHALL preserve valid transition behavior.

#### Scenario: Valid adjacent progression remains available
- **WHEN** no supported blockade is present
- **THEN** narration SHALL preserve availability of authored adjacent travel options

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

