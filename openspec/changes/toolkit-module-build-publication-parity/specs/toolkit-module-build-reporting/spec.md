## ADDED Requirements

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
