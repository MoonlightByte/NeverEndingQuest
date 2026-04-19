## ADDED Requirements

### Requirement: Toolkit SHALL persist an auditable review snapshot for Homebrew upload decisions
The toolkit MUST persist an explicit review snapshot artifact for each approve or reject decision on a Homebrew upload review job.

#### Scenario: Approval writes review snapshot
- **WHEN** the operator approves a review-gated Homebrew upload job
- **THEN** the system MUST persist `ui_review_snapshot.json` in the job workspace
- **AND** the snapshot MUST record the job identifier, decision, review timestamp, and packet identity fields needed for later audit.

#### Scenario: Rejection writes review snapshot
- **WHEN** the operator rejects a review-gated Homebrew upload job
- **THEN** the system MUST persist `ui_review_snapshot.json` in the job workspace
- **AND** the snapshot MUST record the rejection decision without deleting the normalized packet or source artifacts.

### Requirement: Snapshot persistence SHALL be fail-closed for review-state transitions
The toolkit MUST NOT advance a Homebrew upload job into an approved or rejected review state unless the corresponding review snapshot has been persisted successfully.

#### Scenario: Snapshot write failure blocks approval transition
- **WHEN** the system cannot persist the review snapshot for an approval action
- **THEN** the job MUST remain outside `approved_for_build`
- **AND** the system MUST return an explicit review persistence failure to the operator.

#### Scenario: Snapshot write failure blocks rejection transition
- **WHEN** the system cannot persist the review snapshot for a rejection action
- **THEN** the job MUST remain outside `rejected`
- **AND** the workspace artifacts MUST remain available for retry and inspection.
