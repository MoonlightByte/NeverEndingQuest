## Purpose

Define source-scoped memory backfill behavior, selector validation, and idempotent replay guarantees.

## Requirements

### Requirement: Backfill tooling SHALL support explicit source selection
The backfill CLI SHALL accept a source selector argument that allows targeted ingest from specific channels.

#### Scenario: Backfill only journal
- **WHEN** operator runs backfill with `--sources journal`
- **THEN** only journal source entries are processed
- **AND** conversation and combat sources are skipped

#### Scenario: Backfill journal and combat
- **WHEN** operator runs backfill with `--sources journal,combat`
- **THEN** journal and combat sources are processed
- **AND** conversation source is skipped

### Requirement: Source selector MUST validate allowed values
The tool MUST fail fast if unknown source labels are provided.

#### Scenario: Invalid source label
- **WHEN** operator passes `--sources journal,foo`
- **THEN** command exits with non-zero status
- **AND** output clearly lists allowed values (`journal`, `conversation`, `combat`)

### Requirement: Source selection SHALL preserve ingest idempotency
Selective source execution SHALL not change checksum dedupe guarantees for processed records.

#### Scenario: Re-run selective source import
- **WHEN** operator runs `--sources journal` twice against same input
- **THEN** duplicate journal rows are not created
