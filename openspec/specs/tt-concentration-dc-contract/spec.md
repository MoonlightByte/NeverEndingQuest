# tt-concentration-dc-contract Specification

## Purpose
TBD - created by archiving change prompt-validator-save-concentration-contract. Update Purpose after archive.
## Requirements
### Requirement: Concentration DC SHALL use a deterministic 5e formula
Any concentration save DC helper introduced by this change SHALL compute the DC as `max(10, floor(damage / 2))`.

#### Scenario: Low damage concentration hit
- **WHEN** concentration damage is less than 20
- **THEN** the computed concentration DC SHALL be 10

#### Scenario: Higher damage concentration hit
- **WHEN** concentration damage is 23
- **THEN** the computed concentration DC SHALL be 11

### Requirement: Concentration requests SHALL remain compatible with the lightweight roll contract
This change SHALL prepare concentration handling to use explicit roll-request metadata without requiring full result resolution.

#### Scenario: Concentration save request prepared
- **WHEN** runtime or prompts need to ask a player to maintain concentration after taking damage
- **THEN** the resulting request contract SHALL be able to surface a player-facing roll request with a deterministic DC
- **AND** the change SHALL NOT require automatic resolution of that roll in the same phase

