# module-publishability-reporting Specification Delta

## ADDED Requirements

### Requirement: Toolkit reporting SHALL preserve successful build plus media handoff distinction
Publication-facing toolkit reporting SHALL distinguish a successful toolkit build that still requires manual media generation from a true build failure.

#### Scenario: Toolkit report shows build success and media handoff
- **GIVEN** a toolkit module build succeeded structurally
- **AND** manual module media generation remains outstanding
- **WHEN** toolkit reporting is emitted
- **THEN** it SHALL preserve the successful build outcome
- **AND** SHALL expose the outstanding media debt explicitly
- **AND** SHALL name `Module Builder -> Module Media Generator` as the next step
