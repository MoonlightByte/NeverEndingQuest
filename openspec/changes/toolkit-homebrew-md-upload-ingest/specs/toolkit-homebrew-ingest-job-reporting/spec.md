## ADDED Requirements

### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured ingest outcomes using the shared pipeline result contract so users can distinguish `success`, `degraded`, `failed`, and `quarantined` outcomes.

#### Scenario: Structured success result is shown in toolkit
- **WHEN** a toolkit-triggered ingest job completes successfully
- **THEN** the toolkit MUST display the final pipeline status and stage
- **AND** MUST include the resolved module slug in the result summary.

#### Scenario: Quarantined result shows actionable reason
- **WHEN** a toolkit-triggered ingest job is quarantined by preflight, validation, or verification gates
- **THEN** the toolkit MUST display the quarantine reason
- **AND** MUST preserve enough stage detail for the operator to understand which gate failed.

### Requirement: Toolkit job reporting reflects pipeline stages
Toolkit status updates MUST reflect the shared ingest pipeline's stage model rather than a toolkit-only free-form status language.

#### Scenario: Pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results for an ingest job
- **THEN** the reported state MUST include the pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity.
