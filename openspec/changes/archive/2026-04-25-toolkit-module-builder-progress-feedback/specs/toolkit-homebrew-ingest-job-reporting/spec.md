# toolkit-homebrew-ingest-job-reporting Specification Delta

## MODIFIED Requirements

### Requirement: Toolkit job reporting reflects pipeline stages
Toolkit status updates MUST reflect the shared ingest pipeline's stage model rather than a toolkit-only free-form status language. Rebuild-specific pre-build stages such as collision detection, confirmation wait, backup, and clean preparation MUST be surfaced distinctly when they occur. After rebuild preparation hands off to packet-driven module generation, job reporting MUST surface active packet-build progress instead of remaining visually frozen on the rebuild-clean result.

#### Scenario: Pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results for an ingest job
- **THEN** the reported state MUST include the pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity.

#### Scenario: Rebuild preparation stages are visible
- **WHEN** an existing-module collision triggers the backup + clean rebuild flow
- **THEN** the toolkit MUST expose rebuild-preparation progress before packet build begins
- **AND** MUST distinguish those rebuild-preparation states from ordinary fresh-upload build progress.

#### Scenario: Rebuild handoff shows active packet build progress
- **WHEN** rebuild backup and clean preparation have succeeded
- **AND** packet-driven module generation is still running
- **THEN** toolkit job reporting MUST expose the job as actively building
- **AND** MUST include the latest available builder progress message or milestone timestamp
- **AND** MUST preserve rebuild backup metadata in the job details.

## ADDED Requirements

### Requirement: Toolkit Module Builder SHALL expose live progress milestones during long packet builds

The toolkit SHALL surface real ModuleBuilder progress milestones in the polled Homebrew job response while packet-driven builds are running. Progress milestones SHALL be additive to the existing job contract and SHALL NOT replace final structured build, readiness, or publishability results.

#### Scenario: Builder milestone updates active job response

- **WHEN** a packet-driven toolkit build emits a ModuleBuilder milestone such as area, location, plot, summary, validation, or backup generation
- **THEN** the backend SHALL update the job response with a current progress message
- **AND** SHALL update a freshness field such as `progress_updated_at` or `progress_tick`
- **AND** SHALL continue exposing structured job status and stage fields.

#### Scenario: Progress callback failure does not fail build

- **WHEN** a progress callback or job-state progress update raises an exception
- **THEN** the packet build SHALL continue using the existing build pipeline
- **AND** final build success or failure SHALL remain the authoritative outcome
- **AND** the degraded progress reporting failure SHOULD be logged for debugging.

#### Scenario: Frontend prefers latest progress message for active build states

- **WHEN** the toolkit frontend polls an active build job containing `progress_message`
- **THEN** the feedback window SHALL display that message as the current build status
- **AND** SHALL keep structured job details available for troubleshooting
- **AND** SHALL fall back to existing generic active-build text if no progress message is present.
