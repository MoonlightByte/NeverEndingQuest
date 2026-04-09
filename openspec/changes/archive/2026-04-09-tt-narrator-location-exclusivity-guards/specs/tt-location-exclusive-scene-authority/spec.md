## ADDED Requirements

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
