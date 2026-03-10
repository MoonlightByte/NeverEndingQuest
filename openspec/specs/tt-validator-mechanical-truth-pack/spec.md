# tt-validator-mechanical-truth-pack Specification

## Purpose
TBD - created by archiving change prompt-validator-telemetry-and-truth-pack. Update Purpose after archive.
## Requirements
### Requirement: Validator context SHALL use touched-character mechanical truth packs
The validator SHALL receive compact touched-character mechanical truth packs for character mutations in the candidate response.

#### Scenario: Character mutation truth pack
- **WHEN** the candidate response contains `updateCharacterInfo` for one or more characters
- **THEN** validation context SHALL include a compact truth pack for each touched character
- **AND** each truth pack SHALL include HP/max HP, conditions, spell slots, death saves, and class feature usage when present

#### Scenario: Inventory included only when relevant
- **WHEN** the touched change text is inventory-relevant or ambiguous on inventory relevance
- **THEN** the touched-character truth pack SHALL include a compact relevant inventory summary
- **AND** inventory SHALL be omitted for clearly non-inventory mechanical changes

