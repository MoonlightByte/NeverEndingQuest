## ADDED Requirements

### Requirement: Draft Supersede Commit Lifecycle
The system SHALL treat streamed narration as draft content until validation passes, and SHALL finalize user-visible state through explicit supersede and commit lifecycle events.

#### Scenario: Validation failure supersedes draft
- **WHEN** attempt N fails validation
- **THEN** the backend emits `narration_stream_superseded` for attempt N before starting attempt N+1

#### Scenario: Validation success commits latest draft
- **WHEN** attempt N passes validation
- **THEN** the backend emits `narration_stream_commit` for attempt N and does not supersede that committed stream

#### Scenario: Commit uniqueness per turn
- **WHEN** a turn completes successfully
- **THEN** exactly one stream attempt is marked committed for that turn

### Requirement: Canonical History Integrity
The system SHALL persist only committed narration text into canonical conversation history and SHALL NOT persist superseded draft text as accepted output.

#### Scenario: Narrative retry sequence
- **WHEN** one or more retries occur in narrative mode
- **THEN** conversation history persistence includes only the committed attempt text as canonical narration

#### Scenario: Combat retry sequence
- **WHEN** one or more retries occur in combat mode
- **THEN** conversation history persistence includes only the final accepted attempt text as canonical narration

### Requirement: Retry Transparency Without Deadlock
The system SHALL provide retry visibility without leaving input in a permanently locked state.

#### Scenario: Retry progress visibility
- **WHEN** retries are in progress
- **THEN** status messages indicate retry activity while input remains locked

#### Scenario: Terminal unlock on failure
- **WHEN** stream generation reaches terminal failure and cannot recover
- **THEN** status channel transitions back to non-processing state so input is not deadlocked
