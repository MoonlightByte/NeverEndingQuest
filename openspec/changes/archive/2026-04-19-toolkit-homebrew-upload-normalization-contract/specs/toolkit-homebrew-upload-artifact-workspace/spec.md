## ADDED Requirements

### Requirement: Toolkit upload jobs SHALL persist artifacts in a dedicated workspace
Each toolkit Homebrew upload job MUST persist its source and contract artifacts under a dedicated workspace rooted at `user_uploads/toolkit/homebrew_md/<job_id>/`.

#### Scenario: Upload job gets isolated workspace
- **WHEN** a toolkit Homebrew upload job is created
- **THEN** the system MUST assign a unique `job_id`
- **AND** it MUST create a matching dedicated workspace directory for that job

#### Scenario: Workspace is independent of watcher ingest paths
- **WHEN** toolkit upload artifacts are persisted
- **THEN** they MUST NOT be written to watcher-owned `modules/ingest/` locations
- **AND** the toolkit job MUST retain ownership of its artifact workspace

### Requirement: Artifact workspace SHALL preserve canonical filenames for uploader stages
The workspace MUST preserve stable filenames for source, preflight, normalized packet, and later build/report artifacts so later uploader phases can resume or inspect the same job without path drift.

#### Scenario: Core contract artifacts are written with canonical names
- **WHEN** a readable upload enters the toolkit workspace
- **THEN** the workspace MUST contain canonical source and preflight artifacts
- **AND** it MUST reserve canonical filenames for normalized packet and later build/report outputs

#### Scenario: Routing-stop workspace remains inspectable
- **WHEN** a readable upload stops at routing or normalization-required state
- **THEN** the workspace MUST remain on disk for audit and retry
- **AND** the system MUST NOT delete it merely because strict ingest has not started
