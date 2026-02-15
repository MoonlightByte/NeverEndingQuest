## MODIFIED Requirements

### Requirement: Timeline retrieval SHALL be deterministic and ranked
The system SHALL provide `get_entity_timeline` retrieval that returns results in deterministic ranked order using explicit scoring factors, and SHALL ensure one returned row per event with stable tie-break ordering.

#### Scenario: Stable repeated retrieval output
- **WHEN** the same timeline query is executed repeatedly with unchanged data
- **THEN** the returned event ordering is identical across runs

#### Scenario: Multi-link event remains deterministic
- **WHEN** candidate rows include multiple links for the same event
- **THEN** output includes one row for that event
- **AND** relative ordering remains deterministic across repeated runs

### Requirement: Prompt-mode retrieval MUST remain bounded by item and token constraints
The retrieval layer MUST enforce top-K limits, bounded candidate evaluation, and token-cap aware packaging so narrator prompts stay within bounded context budgets.

#### Scenario: Top-K cap enforced
- **WHEN** a retrieval request specifies a limit smaller than total eligible events
- **THEN** the result count does not exceed the requested limit

#### Scenario: Candidate telemetry reflects pre-limit population
- **WHEN** retrieval audit logging is enabled for a bounded query
- **THEN** audit output reports pre-limit candidate count separately from returned result count

### Requirement: Retrieval audit behavior under read-only mode SHALL be explicit
When retrieval runs in read-only mode, audit behavior MUST follow an explicit policy and not rely on implicit sqlite write failures.

#### Scenario: Audit enabled with read-only retrieval
- **WHEN** retrieval is executed with `enable_audit=true`
- **THEN** retrieval queries still execute via read-only connection
- **AND** audit persistence is attempted via dedicated best-effort writer path without creating new DB files
- **AND** failure to persist audit does not fail retrieval response
