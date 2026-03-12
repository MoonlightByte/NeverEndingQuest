## Purpose

Define idempotent, fail-tolerant memory ingestion semantics for journal and history sources.

## Requirements

### Requirement: Journal ingest SHALL be idempotent by source and checksum
The system SHALL deduplicate ingested journal records using source-type and checksum so repeated imports do not create duplicate entries.

#### Scenario: Re-import same journal payload
- **WHEN** the same journal source entry is ingested multiple times with identical checksum
- **THEN** only one persisted journal record exists for that source/checksum pair

### Requirement: Ingestion MUST tolerate partial entry failures
The ingestion pipeline MUST continue processing remaining records if one source entry is malformed, while logging structured error details.

#### Scenario: Mixed valid and invalid batch
- **WHEN** a batch contains one malformed entry and multiple valid entries
- **THEN** valid entries are persisted and malformed entry failure is reported without aborting the full batch

### Requirement: Ingestion SHALL support low-confidence deferred linking
The system SHALL permit storing journal entries without immediate entity links when extraction confidence is insufficient.

#### Scenario: Uncertain entity extraction
- **WHEN** ingest parsing cannot confidently map a journal entry to known entities
- **THEN** the journal entry is stored and link creation is deferred for later enrichment
