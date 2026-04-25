## MODIFIED Requirements

### Requirement: Toolkit surfaces structured Homebrew ingest outcomes and build progression

The toolkit SHALL expose structured status and stage reporting for Homebrew markdown uploads through normalization, auto-started build progression, overwrite-confirmation waits, and terminal outcomes.

#### Scenario: Auto-started build progression remains visible

- **WHEN** a Homebrew markdown upload normalizes successfully and no existing-module collision blocks execution
- **THEN** job reporting exposes the transition from ingest/normalization into active build progression
- **AND** the job status response continues to include structured `status`, `stage`, and artifact metadata

#### Scenario: Existing-module collision remains visible before destruction

- **WHEN** an auto-started packet build resolves to an existing module slug that requires destructive cleanup
- **THEN** job reporting transitions into the existing confirmation-needed state instead of continuing destructively
- **AND** the status payload continues to surface replacement and backup details needed by the operator to confirm or cancel the rebuild
