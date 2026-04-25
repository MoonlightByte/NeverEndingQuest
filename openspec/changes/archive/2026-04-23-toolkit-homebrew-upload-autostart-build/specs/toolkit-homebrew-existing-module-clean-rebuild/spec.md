## MODIFIED Requirements

### Requirement: Existing module rebuild requires explicit destructive confirmation

When a Homebrew markdown upload auto-starts a packet build that targets an existing module slug, the toolkit SHALL pause before destructive cleanup and require explicit operator confirmation, including backup intent, before replacing module contents.

#### Scenario: Auto-started upload pauses only for destructive confirmation

- **WHEN** a normalized Homebrew upload targets an already existing module slug
- **AND** the packet build reaches the rebuild-collision check
- **THEN** the toolkit pauses build execution in the confirmation-needed state
- **AND** the operator is asked whether to create a backup and proceed with cleanup/rebuild
- **AND** the toolkit does not require a separate earlier review approval step

#### Scenario: Backup failure still blocks destructive rebuild

- **WHEN** an operator confirms replacement with backup enabled
- **AND** backup creation fails
- **THEN** destructive cleanup and rebuild do not proceed
- **AND** the failure is surfaced through the existing rebuild reporting path
