# tt-action-contract-parity Specification

## Purpose
TBD - created by archiving change prompt-validator-contract-alignment. Update Purpose after archive.
## Requirements
### Requirement: Covered narrator actions SHALL use one consistent contract across prompt, validator, and runtime
The phase-1 parity slice SHALL ensure that each covered action uses the same action name and parameter contract across narrator prompt text, validator prompt text, and runtime handling.

#### Scenario: Covered action set is explicit for this change
- **WHEN** this OpenSpec change is implemented
- **THEN** the covered phase-1 action set SHALL be explicitly limited to `rest`
- **AND** other known drift such as save/restore/list/delete-save or `createNewModule` SHALL be treated as deferred follow-up work

#### Scenario: Rest action parity
- **WHEN** the covered action is `rest`
- **THEN** the system prompt SHALL document `rest` as a supported action
- **AND** the validation prompt SHALL document `rest` as a supported action
- **AND** runtime SHALL continue to handle `rest` as an executable action

#### Scenario: Covered parameter shape parity
- **WHEN** a covered action has a documented parameter shape
- **THEN** prompt examples and validator parameter references SHALL match the runtime expectation for that covered action
- **AND** stale contradictory parameter contracts SHALL NOT remain in the covered prompt slice

### Requirement: Covered action-contract drift SHALL be regression tested
The repository SHALL include targeted regression coverage that detects drift between the covered prompt slice and runtime action expectations.

#### Scenario: Action coverage regression
- **WHEN** a covered action is removed from either prompt layer while remaining supported in runtime
- **THEN** the parity regression suite SHALL fail

#### Scenario: Contradictory wording regression
- **WHEN** stale validator wording contradicts the covered runtime action contract
- **THEN** the parity regression suite SHALL fail with a contract-drift signal

#### Scenario: Prompt variant parity regression
- **WHEN** either compressed or uncompressed prompt copies drift from the covered runtime contract
- **THEN** the parity regression suite SHALL fail
- **AND** the failure SHALL identify which prompt variant drifted

