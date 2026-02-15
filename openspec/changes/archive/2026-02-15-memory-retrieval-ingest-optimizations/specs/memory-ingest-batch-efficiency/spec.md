## ADDED Requirements

### Requirement: Backfill ingest SHALL reuse a shared DB connection per run
Backfill workflows SHALL use a shared sqlite connection for ingest operations instead of reconnecting for each entry.

#### Scenario: Backfill run processes many entries
- **WHEN** backfill ingests a multi-entry source set
- **THEN** entries are processed through a shared DB connection context

### Requirement: Backfill ingest SHALL use batched transaction boundaries
Backfill workflows SHALL commit via batched transaction boundaries to improve throughput while preserving error tolerance behavior.

#### Scenario: Batch includes malformed and valid entries
- **WHEN** a batch includes malformed entries among valid entries
- **THEN** malformed entries are reported
- **AND** valid entries in successful transaction boundaries remain persisted

### Requirement: Backfill ingest SHALL preserve source chronology when available
Ingested event timestamps SHALL prefer source-provided timestamps when available, with deterministic fallback when source timestamps are absent.

#### Scenario: History entry includes source timestamp
- **WHEN** backfill ingests an entry that includes parseable source timestamp metadata
- **THEN** persisted memory event timestamp reflects the source timestamp rather than ingest-now time
