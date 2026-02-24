## MODIFIED Requirements

### Requirement: Shared audit pipeline SHALL gate manual edit persistence
Manual Roll Your Own edit persistence SHALL invoke the same canonical normalization and audit pipeline used for creation before writing character files.

#### Scenario: Edit payload passes audit
- **WHEN** merged edit payload satisfies schema and completeness checks
- **THEN** edit persistence proceeds and returns success

#### Scenario: Edit payload fails audit
- **WHEN** merged edit payload fails schema or completeness checks
- **THEN** save is blocked, structured validation errors are returned, and existing character file remains unchanged

### Requirement: Audit-gated edit path SHALL remain deterministic
Manual edit route SHALL remain deterministic and SHALL not invoke LLM-based update flows.

#### Scenario: Edit route handling contract
- **WHEN** Roll Your Own edit submit is processed
- **THEN** the route applies deterministic field mapping and audit gating without calling `updateCharacterInfo`
