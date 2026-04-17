## ADDED Requirements

### Requirement: Toolkit SHALL define a canonical normalized packet for readable Homebrew uploads
The toolkit upload pipeline MUST define a canonical normalized packet artifact for readable Homebrew markdown sources that require interpretation before module build or deterministic ingest can proceed.

#### Scenario: Readable source creates packet placeholder
- **WHEN** a toolkit Homebrew markdown upload is readable but routes to normalization-required handling
- **THEN** the system MUST persist `normalized_packet.json` in the upload workspace
- **AND** the packet MUST use the canonical contract shape defined for the uploader lane

#### Scenario: Packet carries source identity and routing state
- **WHEN** `normalized_packet.json` is created for a readable upload
- **THEN** it MUST include `source_path`, `source_hash`, and a packet contract version field
- **AND** it MUST record that interpretation is pending rather than pretending a build-ready structure already exists

### Requirement: Normalized packet SHALL capture provenance and policy fields required by later uploader phases
The normalized packet MUST preserve provenance and policy metadata needed by later review, build, and v2 import phases.

#### Scenario: Rights classification is preserved
- **WHEN** the packet is created
- **THEN** it MUST include `source_rights_class`
- **AND** that field MUST be one of the uploader-approved provenance classes for the module lane

#### Scenario: Review and v2 alignment metadata are reserved
- **WHEN** the packet is created
- **THEN** it MUST include `review_policy` and `v2_alignment`
- **AND** those fields MUST remain available for later review and bulk-import compatibility without renaming the packet contract

### Requirement: Normalized packet SHALL reserve structured interpretation fields without inventing final content prematurely
The normalized packet MUST reserve the structured interpretation fields expected by later normalization/build phases while keeping unresolved interpretation state explicit.

#### Scenario: Reserved interpretation fields exist for pending normalization
- **WHEN** the packet is created before the LLM normalizer exists
- **THEN** it MUST reserve fields for metadata, locations, NPC seeds, monster refs, plot progression, assumptions, warnings, and confidence notes
- **AND** unresolved fields MUST be represented as empty, null, or pending-state values rather than omitted ad hoc
