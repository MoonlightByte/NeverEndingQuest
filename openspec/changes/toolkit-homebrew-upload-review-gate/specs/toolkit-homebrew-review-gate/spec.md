## ADDED Requirements

### Requirement: Toolkit SHALL enforce a mandatory review gate for normalized Homebrew upload jobs
The toolkit MUST stop normalized packet-backed Homebrew upload jobs at an explicit review boundary before any later build-start or registry-facing path can continue.

#### Scenario: Normalized upload enters awaiting review
- **WHEN** a toolkit Homebrew upload job has a readable normalized packet ready for operator inspection
- **THEN** the job MUST transition to `awaiting_review`
- **AND** the toolkit MUST NOT mark the job as build-ready or complete merely because packet preparation succeeded.

#### Scenario: Unreviewed job cannot advance
- **WHEN** a toolkit Homebrew upload job has not yet been approved
- **THEN** the system MUST reject any attempt to treat it as eligible for build continuation
- **AND** MUST preserve the job workspace and reviewable artifacts for later operator action.

### Requirement: Toolkit SHALL present a curated review summary from the normalized packet
The toolkit MUST show a review panel for review-gated Homebrew upload jobs that exposes the packet fields needed for operator approval without requiring direct raw JSON inspection.

#### Scenario: Review panel shows core packet fields
- **WHEN** the operator opens a review-gated Homebrew upload job in the toolkit
- **THEN** the toolkit MUST display the packet's title, author, description, estimated level range, scene or location summary, major NPCs, monster references, warnings, and assumptions
- **AND** the displayed review data MUST be derived from the persisted normalized packet artifact.

#### Scenario: Missing packet blocks review cleanly
- **WHEN** the toolkit cannot load a valid normalized packet for a review-gated job
- **THEN** the system MUST fail closed for review actions
- **AND** MUST return an actionable review error rather than silently approving or hiding the job.

### Requirement: Toolkit SHALL support explicit approve and reject review actions
The toolkit MUST expose explicit approval and rejection actions for review-gated Homebrew upload jobs and MUST apply server-validated state transitions for each decision.

#### Scenario: Approve moves job to approved-for-build state
- **WHEN** the operator approves a valid review-gated Homebrew upload job
- **THEN** the system MUST transition the job to `approved_for_build`
- **AND** MUST preserve the authoritative stage metadata needed by later build execution.

#### Scenario: Reject keeps artifacts available
- **WHEN** the operator rejects a review-gated Homebrew upload job
- **THEN** the system MUST transition the job to `rejected`
- **AND** MUST keep the artifact workspace available for inspection, retry, or later debugging.
