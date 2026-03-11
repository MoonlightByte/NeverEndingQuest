# tt-combat-concentration-request-dc Specification

## Purpose
TBD - created by archiving change combat-save-concentration-contract. Update Purpose after archive.
## Requirements
### Requirement: Combat concentration requests SHALL use deterministic DC contract
The multi-PC combat prompt and combat validator SHALL treat concentration save requests as deterministic requests using `max(10, floor(damage / 2))`.

#### Scenario: Combat concentration request after low damage hit
- **WHEN** a concentration hit deals less than 20 damage
- **THEN** the combat concentration request SHALL use DC 10

#### Scenario: Combat concentration request after higher damage hit
- **WHEN** a concentration hit deals 23 damage
- **THEN** the combat concentration request SHALL use DC 11

### Requirement: Combat concentration requests SHALL remain pause-only
This change SHALL keep combat concentration handling at the request stage only.

#### Scenario: Concentration request stops without contingent resolution
- **WHEN** a combat response emits a concentration `requestRoll`
- **THEN** that response SHALL stop after the request
- **AND** it SHALL NOT narrate contingent save success or failure in the same response

### Requirement: Combat concentration prose fallback SHALL remain valid during migration
This change SHALL preserve existing prose concentration prompts while the structured request path is introduced.

#### Scenario: Prose concentration request remains compatibility-valid
- **WHEN** a combat response asks for a concentration save in prose without `requestRoll`
- **THEN** it SHALL remain compatibility-valid in this change

