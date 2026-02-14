## ADDED Requirements

### Requirement: Single Visible Narration Path
The system SHALL maintain a single visible narration output path per turn in rollback mode.

#### Scenario: No duplicate draft plus block output
- **WHEN** a turn completes successfully
- **THEN** the user sees one canonical narration output and no duplicate draft/render pair

#### Scenario: Validation retry visibility
- **WHEN** retries occur during response generation
- **THEN** users do not receive partial draft narration; only final accepted canonical output is rendered

#### Scenario: Canonical history integrity
- **WHEN** narration is persisted after turn completion
- **THEN** persisted content corresponds to the canonical block narration path

#### Scenario: Canonical emission path remains explicit
- **WHEN** rollback mode is active
- **THEN** canonical narration is emitted by baseline output-capture flow without stream-helper suppression gates
