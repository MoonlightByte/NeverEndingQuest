## MODIFIED Requirements

### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured upload and ingest job outcomes using authoritative routing and pipeline result fields so users can distinguish early routing states from later `success`, `degraded`, `failed`, and `quarantined` outcomes.

#### Scenario: Normalization-required routing result is shown
- **WHEN** a toolkit-triggered upload job finishes preflight with a readable normalization-required outcome
- **THEN** the toolkit MUST display that routing result explicitly
- **AND** MUST preserve enough detail for the operator to understand that the source was readable but not deterministic-ready

#### Scenario: Quarantined result still shows actionable reason
- **WHEN** a toolkit-triggered upload or ingest job is quarantined by preflight, validation, or verification gates
- **THEN** the toolkit MUST display the quarantine reason
- **AND** MUST preserve enough stage detail for the operator to understand which gate failed

### Requirement: Toolkit job reporting reflects routing and pipeline stages
Toolkit status updates MUST reflect authoritative routing and pipeline stages rather than a toolkit-only free-form status language.

#### Scenario: Early routing stage is preserved during reporting
- **WHEN** the toolkit reports progress or final state for an upload job before strict ingest begins
- **THEN** the reported state MUST preserve the authoritative routing stage or state identity
- **AND** toolkit-specific wording MUST NOT overwrite or hide that authoritative state

#### Scenario: Later pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results after strict ingest has begun
- **THEN** the reported state MUST include the authoritative pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity
