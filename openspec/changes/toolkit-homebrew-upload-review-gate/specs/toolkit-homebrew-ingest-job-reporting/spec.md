## MODIFIED Requirements

### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured upload and ingest outcomes using authoritative routing, review, and pipeline result fields so users can distinguish review-gated states from later `success`, `degraded`, `failed`, and `quarantined` outcomes.

#### Scenario: Review-gated result is shown in toolkit
- **WHEN** a toolkit-triggered Homebrew upload job reaches its review boundary
- **THEN** the toolkit MUST display that review-gated state explicitly
- **AND** MUST preserve enough detail for the operator to understand that packet preparation succeeded but build continuation still requires review.

#### Scenario: Approved-for-build result is shown distinctly
- **WHEN** a toolkit-triggered Homebrew upload job has been approved for later build continuation
- **THEN** the toolkit MUST display `approved_for_build` distinctly from final build completion
- **AND** MUST preserve the job's authoritative routing or stage identity when available.

#### Scenario: Quarantined result shows actionable reason
- **WHEN** a toolkit-triggered ingest job is quarantined by preflight, validation, or verification gates
- **THEN** the toolkit MUST display the quarantine reason
- **AND** MUST preserve enough stage detail for the operator to understand which gate failed.

### Requirement: Toolkit job reporting reflects routing and review stages
Toolkit status updates MUST reflect the authoritative upload routing, review, and pipeline stage model rather than a toolkit-only free-form status language.

#### Scenario: Review stage is preserved during reporting
- **WHEN** the toolkit reports progress or final review-state results for a Homebrew upload job before build starts
- **THEN** the reported state MUST include the authoritative review or routing stage identity when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide that authoritative state.

#### Scenario: Later pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results after strict ingest or later build execution has begun
- **THEN** the reported state MUST include the authoritative pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity.
