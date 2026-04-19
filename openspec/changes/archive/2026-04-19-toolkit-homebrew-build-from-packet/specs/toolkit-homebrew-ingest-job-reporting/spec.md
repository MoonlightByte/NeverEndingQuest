## MODIFIED Requirements

### Requirement: Toolkit exposes structured ingest job outcomes
The toolkit MUST expose structured upload and ingest outcomes using authoritative routing, normalization, review, and packet-build fields so users can distinguish review readiness, packet-driven build progress, and later finishing outcomes.

#### Scenario: Approved-for-build state is shown distinctly
- **WHEN** a reviewed upload job is waiting for explicit build start
- **THEN** the toolkit MUST display `approved_for_build` distinctly
- **AND** it MUST communicate that the job is approved but not yet building.

#### Scenario: Packet-driven building state is shown explicitly
- **WHEN** a toolkit Homebrew upload job is running the packet-driven builder
- **THEN** the toolkit MUST display `building` explicitly
- **AND** MUST preserve enough detail for the operator to understand that later finishing/publication has not yet run.

#### Scenario: Build-complete state remains distinct from final completion
- **WHEN** a packet-driven build succeeds before finisher integration exists
- **THEN** the toolkit MUST display a distinct pre-finishing build success state such as `build_completed`
- **AND** it MUST NOT collapse that state into final `completed` reporting.

### Requirement: Toolkit job reporting reflects routing, normalization, review, and build stages
Toolkit status updates MUST reflect the authoritative upload routing, normalization, review, and packet-build stage model rather than a toolkit-only free-form status language.

#### Scenario: Packet-build stage identity is preserved during reporting
- **WHEN** the toolkit reports progress or failure for a Homebrew upload job after explicit build start
- **THEN** the reported state MUST include the authoritative build stage identity when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide that authoritative state.

#### Scenario: Later pipeline stage is preserved during reporting
- **WHEN** the toolkit reports progress or final results after strict ingest or later finisher execution has begun
- **THEN** the reported state MUST include the authoritative later pipeline `stage` field when available
- **AND** toolkit-specific wording MUST NOT overwrite or hide the authoritative pipeline stage identity.
