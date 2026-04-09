# journal-cadence-transition-and-long-rest-checkpoints Specification

## Purpose
TBD - created by archiving change players-diary-journal-cadence-hardening. Update Purpose after archive.
## Requirements
### Requirement: Journal cadence SHALL use transitions and completed long rests
The system SHALL preserve location-transition journal checkpoints and SHALL add long-rest journal checkpoints as an additional source of reflective journal updates.

#### Scenario: Transition still creates a journal checkpoint
- **WHEN** a valid same-module location transition is processed through the existing checkpoint path
- **THEN** the system SHALL continue to append one journal checkpoint for that transition

#### Scenario: Long rest creates a journal checkpoint after successful completion
- **WHEN** a long rest completes successfully
- **AND** meaningful unjournaled gameplay delta exists since the previous successful journal checkpoint
- **THEN** the system SHALL append one journal checkpoint for that long rest

#### Scenario: Short rest does not journal by default
- **WHEN** a short rest completes successfully
- **THEN** the system SHALL NOT create a journal checkpoint by default in this change

### Requirement: Long-rest journaling SHALL be fail-open
Long-rest journal checkpoint generation MUST NOT block or undo a successful long rest.

#### Scenario: Journal generation degrades after long rest success
- **WHEN** a long rest completes successfully
- **AND** journal checkpoint generation fails or returns unusable output
- **THEN** the long rest SHALL remain successful
- **AND** no partial or duplicate journal checkpoint SHALL be committed

