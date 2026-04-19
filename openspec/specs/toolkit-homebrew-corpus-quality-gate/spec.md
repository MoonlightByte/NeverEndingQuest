# toolkit-homebrew-corpus-quality-gate Specification

## Purpose
TBD - created by archiving change toolkit-homebrew-corpus-quality-gate. Update Purpose after archive.
## Requirements
### Requirement: Corpus Fixture Acceptance Gate
The public Homebrew uploader SHALL provide a repeatable corpus-based acceptance gate for representative Homebrew markdown fixtures.

#### Scenario: Tracked canonical corpus is repo-portable
- **GIVEN** the canonical Phase 8 acceptance corpus is defined
- **WHEN** the corpus gate is implemented in committed code and tests
- **THEN** the canonical corpus is sourced from tracked in-repo fixtures
- **AND** no developer-local or private default path is required for the baseline gate

#### Scenario: Optional external corpus is operator supplied only
- **GIVEN** an operator wants to run an extended corpus beyond the tracked baseline
- **WHEN** external corpus support is used
- **THEN** it requires explicit operator-supplied input
- **AND** no committed default private path is hardcoded

#### Scenario: Missing optional external fixture is skipped explicitly
- **GIVEN** an operator-supplied external corpus fixture path does not exist in the local environment
- **WHEN** the corpus gate runs
- **THEN** that fixture is reported as skipped with an explicit reason
- **AND** the overall run does not fail solely because the external fixture is unavailable

#### Scenario: Readable fixture reaches bounded classified outcome
- **GIVEN** a readable corpus fixture is available
- **WHEN** the corpus gate runs the uploader workflow for that fixture
- **THEN** the fixture reaches one bounded classified outcome of `publishable_pass`, `not_publishable_bounded`, `finishing_failed_bounded`, or `quarantined_bounded`
- **AND** any unclassified hard error fails the gate

### Requirement: Developer And Uploader Outcome Parity
The corpus gate SHALL verify contract-level parity between developer ingest finishing outcomes and public uploader terminal outcomes for representative fixtures.

#### Scenario: Publishable parity maps to uploader completion
- **GIVEN** a representative fixture where developer ingest reports `ready_status=pass` and `publishable_status=pass`
- **WHEN** parity is evaluated against the public uploader result
- **THEN** the uploader outcome is classified as publishable success
- **AND** the parity check passes

#### Scenario: Blocked publishability maps to not publishable
- **GIVEN** a representative fixture where developer ingest reports `ready_status=pass` and `publishable_status!=pass`
- **WHEN** parity is evaluated against the public uploader result
- **THEN** the uploader outcome maps to `not_publishable` or an equivalent bounded blocked classification
- **AND** the parity check passes only if blocker semantics align

### Requirement: Operator-Facing Corpus Summary
The corpus gate SHALL emit a bounded operator-facing summary suitable for release sign-off.

#### Scenario: Summary reports attempted and skipped fixtures
- **GIVEN** the corpus gate finishes running
- **WHEN** the summary is produced
- **THEN** it includes attempted fixtures, skipped fixtures with reason, terminal classification per runnable fixture, parity result, and overall gate status
- **AND** it does not require reading raw artifact files to understand the result

