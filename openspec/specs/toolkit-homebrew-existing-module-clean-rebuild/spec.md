# toolkit-homebrew-existing-module-clean-rebuild Specification

## Purpose
TBD - created by archiving change toolkit-homebrew-existing-module-clean-rebuild. Update Purpose after archive.
## Requirements
### Requirement: Existing module rebuild requires explicit destructive confirmation
When a Homebrew markdown upload auto-starts packet build and resolves to a module slug that already exists on disk, the toolkit MUST require explicit operator confirmation before any destructive rebuild action begins.

#### Scenario: Existing module collision pauses build start
- **WHEN** an auto-started Homebrew upload reaches packet build and `modules/<derived-slug>` already exists
- **THEN** the toolkit MUST stop before backup, cleanup, or builder execution begins
- **AND** MUST present a user-visible confirmation that the existing module will be replaced through a backup + clean rebuild flow
- **AND** MUST NOT require a separate earlier review approval step.

#### Scenario: Operator cancels repeated-upload rebuild
- **WHEN** the operator declines the rebuild confirmation for an existing module collision
- **THEN** the toolkit MUST leave the existing module directory untouched
- **AND** MUST NOT start packet build or readiness stages for that upload.

### Requirement: Confirmed repeated upload uses backup plus clean rebuild
Confirmed repeated uploads MUST preserve a recoverable backup of the existing module directory and MUST rebuild into a clean target directory before packet build starts.

#### Scenario: Confirmed rebuild creates backup before cleanup
- **WHEN** the operator confirms rebuild for an existing module collision
- **THEN** the toolkit MUST create a backup of the existing module directory before deleting or clearing the active target directory
- **AND** MUST record the backup path in the rebuild result or job state.

#### Scenario: Backup failure blocks destructive rebuild
- **WHEN** the toolkit cannot create the backup for an existing module collision
- **THEN** the toolkit MUST stop the rebuild before cleanup begins
- **AND** MUST preserve the existing active module directory unchanged
- **AND** MUST return a bounded failure result describing the backup failure.

#### Scenario: Clean rebuild resumes existing packet pipeline
- **WHEN** backup succeeds and the active target directory is cleaned
- **THEN** the toolkit MUST resume the normal packet-driven build and structural readiness pipeline for that upload
- **AND** the repeated upload MUST use the same post-clean validation path as a fresh upload.
