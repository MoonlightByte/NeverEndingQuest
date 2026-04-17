## MODIFIED Requirements

### Requirement: Metadata Completeness Check
The tool SHALL verify required metadata fields are present, but it SHALL treat missing metadata on a readable source as a fixable routing signal rather than proof that the source is unusable.

#### Scenario: Missing required metadata on readable source
- **WHEN** a readable source lacks `author` or `description`
- **THEN** preflight SHALL report `metadata_missing` with severity `fixable`
- **AND** the source SHALL remain eligible for normalization-required routing
- **AND** preflight SHALL NOT classify the source as unreadable solely because metadata is missing

#### Scenario: Complete metadata with deterministic-ready structure
- **WHEN** a readable source includes title, author, and description and also satisfies deterministic structure checks
- **THEN** preflight SHALL preserve deterministic-ready eligibility

### Requirement: Structure Classification
The tool SHALL classify source structure for routing and SHALL distinguish deterministic-ready structure from readable structure that requires later interpretation.

#### Scenario: Room-based structure detected
- **WHEN** a source contains `## Room 1:` style headers
- **THEN** `structure_class` SHALL be `room_based`
- **AND** the source SHALL be eligible for deterministic-ready routing

#### Scenario: ACT/LOCATION structure detected
- **WHEN** a source contains `## ACT` and `### LOCATIONS` headers
- **THEN** `structure_class` SHALL be `act_location`
- **AND** deterministic readiness SHALL still depend on parseability

#### Scenario: Readable but non-deterministic structure
- **WHEN** a source is readable but does not match supported deterministic structure patterns
- **THEN** preflight SHALL classify the structure as non-deterministic or unknown
- **AND** the source SHALL be eligible for normalization-required routing
- **AND** preflight SHALL NOT reject it as unreadable solely because its structure is ambiguous

### Requirement: JSON Output Mode
The tool SHALL support structured JSON output and SHALL include routing-oriented fields needed by the toolkit upload job layer.

#### Scenario: JSON flag provided
- **WHEN** the `--json` flag is passed
- **THEN** output SHALL be valid JSON with the documented schema
- **AND** it SHALL preserve `issues`, `ready`, `can_auto_transform`, and `structure_class`

#### Scenario: Readable source requires normalization routing
- **WHEN** preflight determines that a source is readable but not deterministic-ready
- **THEN** JSON output SHALL expose a routing outcome that indicates normalization is required
- **AND** it SHALL preserve fixable issue details without collapsing to a generic unreadable-source failure
