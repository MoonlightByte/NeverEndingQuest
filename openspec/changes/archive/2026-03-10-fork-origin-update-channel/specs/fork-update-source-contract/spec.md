## ADDED Requirements

### Requirement: Version check SHALL resolve update source from fork origin
The system SHALL resolve update ownership from git `origin` remote and SHALL NOT hardcode upstream repository coordinates.

#### Scenario: Origin resolves to fork repository
- **WHEN** `origin` is configured as `https://github.com/zeug-zz/NeverEndingQuest-TTRPG.git`
- **THEN** version check targets `zeug-zz/NeverEndingQuest-TTRPG`
- **AND** update status compares local version against fork metadata

#### Scenario: Origin is missing or malformed
- **WHEN** resolver cannot parse `origin`
- **THEN** status returns `unknown`
- **AND** no update-available assertion is emitted

### Requirement: GUI update SHALL use explicit fork fast-forward pull
The updater SHALL execute explicit fork pull commands and SHALL fail closed on preflight or git errors.

#### Scenario: Clean tree and fast-forward available
- **WHEN** worktree is clean and `origin/main` is ahead
- **THEN** updater runs fetch and `pull --ff-only` against fork target
- **AND** emits `update_complete` on success

#### Scenario: Dirty tree blocks update
- **WHEN** local worktree has staged or unstaged modifications
- **THEN** updater emits `update_error` with operator guidance
- **AND** does not run pull/install mutations

#### Scenario: Fast-forward not possible
- **WHEN** pull requires merge or rebase
- **THEN** updater emits `update_error`
- **AND** process remains running without partial restart

### Requirement: Update UI SHALL identify fork-sourced channel
The update button/dialog text SHALL communicate fork-channel behavior.

#### Scenario: Update available status emitted
- **WHEN** backend emits `version_status` with `update_available=true`
- **THEN** UI text indicates update is from fork target
- **AND** does not reference upstream ownership
