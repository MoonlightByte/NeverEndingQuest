# load-dialog-action-compatibility Specification

## Purpose
TBD - created by archiving change load-dialog-unified-archive-save-timeline. Update Purpose after archive.
## Requirements
### Requirement: Restore action SHALL remain entry-type compatible
Unified list selection SHALL dispatch restore actions by entry type using existing handlers.

#### Scenario: Restore selected save folder
- **WHEN** selected entry has `entry_type=save_folder`
- **THEN** frontend emits restore payload through existing `restoreGame` action path

#### Scenario: Restore selected archive zip
- **WHEN** selected entry has `entry_type=archive_zip`
- **THEN** frontend emits restore payload through existing `restoreArchiveZip` action path

### Requirement: Delete action SHALL remain restricted to save folders
Delete control SHALL only be enabled for save-folder entries.

#### Scenario: Archive zip selected
- **WHEN** selected entry has `entry_type=archive_zip`
- **THEN** delete control remains disabled

### Requirement: Existing backend contract SHALL remain unchanged
Unifying presentation SHALL NOT require renaming existing socket events or payload shapes.

#### Scenario: Existing events continue working
- **WHEN** frontend requests load data
- **THEN** backend continues emitting `save_list_response` and `archive_zip_list_response`
- **AND** unified rendering uses those payloads without API contract changes

