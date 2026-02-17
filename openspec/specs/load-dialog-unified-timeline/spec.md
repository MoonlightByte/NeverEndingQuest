# load-dialog-unified-timeline Specification

## Purpose
TBD - created by archiving change load-dialog-unified-archive-save-timeline. Update Purpose after archive.
## Requirements
### Requirement: Load dialog SHALL present a unified timeline across entry types
The Load dialog SHALL render save folders and archive zips within one merged list.

#### Scenario: Merged list includes both payload sources
- **WHEN** frontend receives `save_list_response` and `archive_zip_list_response`
- **THEN** frontend normalizes both datasets into one entry list
- **AND** both save-folder and archive-zip rows are rendered in the same list container

### Requirement: Unified timeline SHALL sort by recency across types
The merged list SHALL sort newest-first using a shared timestamp sort key regardless of entry type.

#### Scenario: Newer archive appears above older save folder
- **GIVEN** an archive zip with a newer timestamp than at least one save folder
- **WHEN** the list is rendered
- **THEN** that archive row appears before the older save-folder row

### Requirement: Timeline rendering SHALL remain deterministic when timestamps are missing
If one or more entries have missing or invalid timestamps, rendering SHALL remain stable and deterministic.

#### Scenario: Entry missing timestamp
- **WHEN** an entry has no valid timestamp
- **THEN** renderer applies fallback ordering keys
- **AND** list rendering does not throw errors

