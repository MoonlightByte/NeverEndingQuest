## ADDED Requirements

### Requirement: Journal cadence checkpoints SHALL be idempotent
Transition and long-rest journal cadence hooks SHALL use deterministic duplicate suppression so the same checkpoint cannot create multiple journal rows on retries, resume flows, or repeated processing.

#### Scenario: Reprocessing the same transition does not duplicate a row
- **WHEN** the system re-evaluates a transition that already produced a journal checkpoint
- **THEN** it SHALL NOT append a second journal row for the same checkpoint

#### Scenario: Reprocessing the same long rest does not duplicate a row
- **WHEN** the system re-evaluates a long-rest checkpoint that already produced a journal row
- **THEN** it SHALL NOT append a second journal row for the same checkpoint

### Requirement: No-delta rest checkpoints SHALL no-op
The system SHALL suppress long-rest journaling when there is no meaningful unjournaled gameplay delta since the previous successful journal checkpoint.

#### Scenario: Transition followed immediately by long rest avoids duplicate summary
- **WHEN** a long rest occurs immediately after a transition-created checkpoint
- **AND** no meaningful new gameplay delta exists beyond the already-journaled transition beat
- **THEN** the long-rest cadence hook SHALL no-op instead of appending a near-duplicate journal row
