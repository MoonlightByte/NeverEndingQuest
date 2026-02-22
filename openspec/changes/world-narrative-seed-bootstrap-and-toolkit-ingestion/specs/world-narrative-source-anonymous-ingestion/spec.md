## ADDED Requirements

### Requirement: Source-anonymous ingest MUST fail-closed on compliance violations
The ingestion service MUST reject payloads that contain banned source-identifying keys or terms.

#### Scenario: Banned key detected
- **WHEN** payload includes banned key names (for example `title`, `author`, `source`)
- **THEN** ingest is rejected with compliance error details

#### Scenario: Banned term detected
- **WHEN** payload includes configured banned terms in string values
- **THEN** ingest is rejected with matched term/path details

### Requirement: Atom ingest SHALL upsert anonymous profiles and atoms deterministically
The ingestion service SHALL upsert source-anonymous profile/atom records and update atom statistics deterministically.

#### Scenario: First ingest of atom set
- **WHEN** a valid new payload is ingested
- **THEN** profile and atom rows are created and statistics are initialized

#### Scenario: Reingest of overlapping atom set
- **WHEN** payload includes previously ingested atom IDs
- **THEN** atoms are updated and statistics support/weight fields are updated without duplicate rows

### Requirement: Ingest outputs MUST exclude raw source identifiers
The ingestion layer MUST not persist raw source file metadata or bibliographic identifiers into committable world-narrative tables.

#### Scenario: Valid source-anonymous payload ingest
- **WHEN** payload passes compliance checks
- **THEN** persisted rows contain only source-anonymous fields required by schema
