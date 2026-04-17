## MODIFIED Requirements

### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured upload and ingest outcomes using authoritative routing, normalization, review, and pipeline result fields so users can distinguish normalization progress from later review and build outcomes.

#### Scenario: Normalizing state is shown explicitly
- **WHEN** a toolkit-triggered Homebrew upload job is running the normalization engine
- **THEN** the toolkit MUST display `normalizing` explicitly
- **AND** MUST preserve enough detail for the operator to understand that review is not yet available.

#### Scenario: Awaiting review only appears after successful normalization
- **WHEN** a toolkit-triggered Homebrew upload job has completed normalization successfully
- **THEN** the toolkit MUST display `awaiting_review` only after packet, report, and builder narrative artifacts are available
- **AND** MUST NOT use `awaiting_review` for routing-only placeholder states.

#### Scenario: Quarantined result shows actionable reason
- **WHEN** a toolkit-triggered ingest job is quarantined by preflight, validation, or verification gates
- **THEN** the toolkit MUST display the quarantine reason
- **AND** MUST preserve enough stage detail for the operator to understand which gate failed.

### Requirement: Toolkit job reporting reflects routing, normalization, and review stages
Toolkit status updates MUST reflect the authoritative upload routing, normalization, review, and pipeline stage model rather than a toolkit-only free-form status language.

#### Scenario: Normalization stage identity is preserved during reporting
- **WHEN** the toolkit reports progress or failure for a Homebrew upload job before review starts
- **THEN** the reported state MUST include the authoritative normalization or routing stage identity when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide that authoritative state.

#### Scenario: Later pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results after strict ingest or later build execution has begun
- **THEN** the reported state MUST include the authoritative pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity.
