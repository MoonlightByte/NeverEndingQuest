## MODIFIED Requirements

### Requirement: Validator context SHALL use touched-character mechanical truth packs

The validator SHALL receive compact touched-character mechanical truth packs for character mutations in the candidate response.

#### Scenario: Character mutation truth pack
- **WHEN** the candidate response contains `updateCharacterInfo` for one or more characters
- **THEN** validation context SHALL include a compact truth pack for each touched character
- **AND** each truth pack SHALL include HP/max HP, conditions, spell slots, death saves, and class feature usage when present

#### Scenario: Nested feature usage is surfaced
- **WHEN** a touched character stores limited-use feature state under `classFeatures[].usage`
- **THEN** the touched-character truth pack SHALL surface that current/max usage state in compact form
- **AND** SHALL NOT rely only on legacy flat `uses`-style keys

#### Scenario: Inventory included from live schema when relevant
- **WHEN** the touched change text is inventory-relevant or ambiguous on inventory relevance
- **THEN** the touched-character truth pack SHALL include a compact relevant inventory summary built from live `equipment`, `ammunition`, and `currency` state
- **AND** inventory SHALL be omitted for clearly non-inventory mechanical changes
