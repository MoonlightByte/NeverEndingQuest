# toolkit-module-build-reporting Specification

## Purpose
TBD - created by archiving change toolkit-module-build-publication-parity. Update Purpose after archive.
## Requirements
### Requirement: Toolkit build reporting distinguishes generation from finishing
Toolkit build reporting MUST distinguish raw module generation success from post-build finishing outcomes.

#### Scenario: Finishing failure is reported after successful generation
- **WHEN** raw module generation succeeds but a required finishing stage fails
- **THEN** the toolkit MUST report that generation succeeded but finishing failed
- **AND** MUST expose enough detail for the operator to identify the failed finishing stage.

#### Scenario: Degraded finishing is reported explicitly
- **WHEN** the finishing pass completes with degraded-but-usable results
- **THEN** the toolkit MUST report a degraded outcome rather than a plain success message
- **AND** MUST preserve the generated module identity in the result payload.

### Requirement: Toolkit builds persist a post-build report

Toolkit builds MUST persist a machine-readable post-build report or sidecar so parity-stage outcomes can be reviewed outside transient socket messages.

#### Scenario: Post-build report is written

- **WHEN** a toolkit build finishes its post-build parity pass
- **THEN** the system MUST write a machine-readable report tied to the generated module
- **AND** the report MUST include the final top-level status and finishing-stage details.

#### Scenario: MMG completion refreshes persisted report after media debt remediation

- **GIVEN** a module whose persisted toolkit build report still indicates media debt or `Needs Module Media Generator`
- **AND** the module's MMG workflow successfully completes required media generation for that module
- **WHEN** the MMG completion path finalizes successfully
- **THEN** the system SHALL invoke the shared persisted report refresh contract for that module
- **AND** the rewritten `toolkit_build_report.json` SHALL reflect the latest publishability-facing blocker state instead of the stale pre-MMG state.

#### Scenario: MMG report refresh fails open

- **GIVEN** a successful MMG media-generation run for a module
- **AND** the subsequent persisted report refresh path degrades or fails
- **WHEN** the system finalizes the MMG completion flow
- **THEN** the MMG completion result SHALL still report media-generation success to the operator
- **AND** sidebar consumers SHALL remain on the previous persisted report until a later valid refresh path runs
- **AND** the system SHALL NOT substitute live MMG table status for persisted sidebar status.

