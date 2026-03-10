## ADDED Requirements

### Requirement: Toolkit world-source upload MUST be constrained to local uploads path
Toolkit upload endpoints MUST accept only `pdf` files and MUST store uploaded files under `/user_uploads/text/`.

#### Scenario: Allowed upload
- **WHEN** user uploads a supported file type with attestation enabled
- **THEN** file is saved under `/user_uploads/text/` and response returns success metadata

#### Scenario: Unsupported file type or missing attestation
- **WHEN** user uploads disallowed extension or skips attestation
- **THEN** request fails with 4xx error and no file is accepted

#### Scenario: Legacy upload root is used
- **WHEN** a request references files under legacy `/user_uploads/` paths outside `/user_uploads/text/`
- **THEN** request fails with 4xx error and no job is started

### Requirement: Toolkit ingestion job flow SHALL enforce one active job
Toolkit extraction/build pipelines SHALL enforce one-active-job semantics to prevent concurrent context-heavy processing.

#### Scenario: No active job
- **WHEN** extract job is requested and lock is free
- **THEN** job starts and returns `job_id`

#### Scenario: Active job exists
- **WHEN** a second extract job is requested during active processing
- **THEN** request returns conflict response with active job reference

### Requirement: Toolkit ingest endpoint MUST fail-closed on compliance failures
The toolkit ingest endpoint MUST validate atom payload compliance before database writes.

#### Scenario: Compliance failure
- **WHEN** atoms payload fails banned key/term checks
- **THEN** endpoint returns error and no DB writes occur

#### Scenario: Compliance pass
- **WHEN** atoms payload passes validation
- **THEN** endpoint ingests anonymous atoms and returns ingest summary
