# campaign-reset-memory-backup-parity Specification

## Purpose
TBD - created by archiving change archive-zip-portability-and-memory-backup-parity. Update Purpose after archive.
## Requirements
### Requirement: Nuclear reset backup SHALL capture memory state artifacts
The nuclear reset backup workflow SHALL explicitly include memory state artifacts so rollback backups preserve memory parity with gameplay state.

#### Scenario: Memory DB exists at backup time
- **WHEN** `data/memory.db` exists during reset backup creation
- **THEN** backup output includes memory state artifact in the backup directory

### Requirement: Memory backup capture SHALL be non-fatal when memory DB is absent
If no memory DB artifact exists, reset backup SHALL continue successfully and record that memory artifact was not present.

#### Scenario: No memory DB available
- **WHEN** reset backup runs and no memory DB file is present
- **THEN** reset backup completes without failure and reports memory artifact absence in output/status

### Requirement: Memory backup artifacts SHALL not break existing reset flow
Adding memory artifact capture SHALL remain additive and SHALL NOT change existing module reset and cleanup semantics.

#### Scenario: Existing reset phases still execute
- **WHEN** reset backup includes memory artifact capture logic
- **THEN** module backup, module reset, global state reset, and cleanup phases still execute in established order

