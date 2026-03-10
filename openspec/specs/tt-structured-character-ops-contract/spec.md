# tt-structured-character-ops-contract Specification

## Purpose
TBD - created by archiving change prompt-validator-structured-ops-pilot. Update Purpose after archive.
## Requirements
### Requirement: `updateCharacterInfo` SHALL support additive structured ops
`updateCharacterInfo.parameters` SHALL support an additive `ops` field without breaking legacy `changes` support.

#### Scenario: Legacy prose payload remains valid
- **WHEN** the narrator emits `updateCharacterInfo` with only `characterName` and `changes`
- **THEN** the payload SHALL remain valid

#### Scenario: Mixed payload remains valid
- **WHEN** the narrator emits `updateCharacterInfo` with `characterName`, `changes`, and `ops`
- **THEN** the payload SHALL remain valid
- **AND** the structured `ops` contract SHALL be recognized

### Requirement: Initial supported ops set SHALL be explicit
The initial supported structured ops set SHALL be documented consistently across prompts, validator, and runtime tests.

#### Scenario: Supported ops set documented
- **WHEN** the contract is reviewed
- **THEN** it SHALL explicitly include `set_hp`, `hp_delta`, `spell_slot_delta`, `inventory_add`, `inventory_remove`, `currency_delta`, `condition_add`, and `condition_remove`

