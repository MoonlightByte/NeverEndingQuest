## ADDED Requirements

### Requirement: Toolkit SHALL normalize readable Homebrew markdown into a source-faithful packet
The toolkit MUST provide a normalization engine that interprets readable Homebrew markdown into a persisted normalized packet suitable for later human review.

#### Scenario: Readable ambiguous source produces normalized packet
- **WHEN** a toolkit Homebrew upload is readable but requires interpretation before deterministic ingest or build
- **THEN** the system MUST generate `normalized_packet.json`
- **AND** the packet MUST contain structured reviewable fields derived from the uploaded source rather than placeholder-only routing data.

#### Scenario: Missing metadata is inferred during normalization
- **WHEN** a readable upload is missing metadata such as author or description
- **THEN** the normalization engine MUST attempt to infer those fields from source context
- **AND** it MUST preserve whether that content is grounded or inferred in the packet or report artifacts.

### Requirement: Normalization SHALL separate grounded facts from assumptions
The normalization engine MUST preserve a clear distinction between source-grounded content and inferred assumptions.

#### Scenario: Assumptions are recorded explicitly
- **WHEN** the normalizer must infer structure, connectivity, or metadata not stated explicitly in the source
- **THEN** the system MUST record those inferences as assumptions, warnings, or equivalent non-grounded fields
- **AND** it MUST NOT silently present them as guaranteed source facts.

#### Scenario: Grounded packet content remains source-faithful
- **WHEN** the source provides explicit scenes, NPCs, monsters, or plot beats
- **THEN** the normalizer MUST preserve those elements faithfully in the packet
- **AND** it MUST NOT introduce freeform new branches without explicit assumption marking.

### Requirement: Successful normalization SHALL persist packet, report, and builder narrative artifacts
The toolkit MUST persist the core normalization artifacts required for later review and build handoff.

#### Scenario: Core normalization artifacts are written together
- **WHEN** normalization succeeds
- **THEN** the system MUST persist `normalized_packet.json`, `normalization_report.json`, and `builder_narrative.txt`
- **AND** those artifacts MUST remain in the upload workspace for later review, retry, and build phases.

#### Scenario: Persistence failure blocks review handoff
- **WHEN** any required normalization artifact cannot be persisted
- **THEN** the job MUST NOT transition to review-ready state
- **AND** the system MUST surface a normalization failure to the operator.
