# load-dialog-entry-filters Specification

## Purpose
TBD - created by archiving change load-dialog-unified-archive-save-timeline. Update Purpose after archive.
## Requirements
### Requirement: Load dialog SHALL provide entry-type filters
The Load dialog SHALL provide filter controls for `all`, `save_folders`, and `archive_zips`.

#### Scenario: Default filter on open
- **WHEN** operator opens the Load dialog
- **THEN** active filter defaults to `all`
- **AND** merged list shows both entry types

### Requirement: Filtering SHALL limit rendered entries by selected type
Filter selection SHALL constrain visible rows to the selected type without changing source payloads.

#### Scenario: Archive filter selected
- **WHEN** operator selects `archive_zips`
- **THEN** list shows only `entry_type=archive_zip` rows
- **AND** save-folder rows are hidden

### Requirement: Filter state SHALL update selection safety
If a selected item becomes hidden by filter selection, selection SHALL be cleared and controls updated.

#### Scenario: Selected save folder hidden by archive filter
- **GIVEN** a save-folder row is selected
- **WHEN** operator switches filter to `archive_zips`
- **THEN** prior selection is cleared
- **AND** action buttons reflect current selection availability

