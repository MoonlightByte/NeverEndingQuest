# toolkit-homebrew-ingest-job-reporting Specification

## Purpose
TBD - created by archiving change toolkit-homebrew-md-upload-ingest. Update Purpose after archive.
## Requirements
### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured ingest outcomes using the shared pipeline result contract so users can distinguish `success`, `degraded`, `failed`, and `quarantined` outcomes. For repeated Homebrew uploads that rebuild an existing module, the toolkit MUST also expose whether the run is a confirmed rebuild and MUST preserve backup outcome details in the result surface.

#### Scenario: Structured success result is shown in toolkit
- **WHEN** a toolkit-triggered ingest job completes successfully
- **THEN** the toolkit MUST display the final pipeline status and stage
- **AND** MUST include the resolved module slug in the result summary.

#### Scenario: Quarantined result shows actionable reason
- **WHEN** a toolkit-triggered ingest job is quarantined by preflight, validation, or verification gates
- **THEN** the toolkit MUST display the quarantine reason
- **AND** MUST preserve enough stage detail for the operator to understand which gate failed.

#### Scenario: Confirmed rebuild result preserves backup metadata
- **WHEN** a repeated Homebrew upload rebuilds an existing module after operator confirmation
- **THEN** the toolkit MUST report that the run used rebuild mode
- **AND** MUST include the backup result or backup path in the job details.

### Requirement: Toolkit job reporting reflects pipeline stages
Toolkit status updates MUST reflect the shared ingest pipeline's stage model rather than a toolkit-only free-form status language. Rebuild-specific pre-build stages such as collision detection, confirmation wait, backup, and clean preparation MUST be surfaced distinctly when they occur.

#### Scenario: Pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results for an ingest job
- **THEN** the reported state MUST include the pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity.

#### Scenario: Rebuild preparation stages are visible
- **WHEN** an existing-module collision triggers the backup + clean rebuild flow
- **THEN** the toolkit MUST expose rebuild-preparation progress before packet build begins
- **AND** MUST distinguish those rebuild-preparation states from ordinary fresh-upload build progress.

