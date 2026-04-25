# module-semantic-authority-enrichment Specification Delta

## ADDED Requirements

### Requirement: Plot titles with authoritative location binding SHALL not create free-floating destination blockers
When a plot point already binds to canonical location identity through `location` or `involvedLocations`, semantic-authority enrichment SHALL NOT treat the plot point title as destination-eligible phrase authority.

#### Scenario: Authoritative plot title does not emit unresolved destination phrases
- **GIVEN** a plot point title contains destination-like wording such as `Echoes Beneath: Unrest in the Catacombs`
- **AND** the same plot point already binds to canonical location `CBTC004`
- **WHEN** semantic-authority enrichment runs
- **THEN** the title SHALL NOT generate unresolved canonical destination phrases like `catacombs` or `unrest in the catacombs`
- **AND** the plot point may still contribute non-destination evidence through its other fields.

#### Scenario: Unbound plot title keeps existing destination extraction behavior
- **GIVEN** a plot point title contains destination-like wording
- **AND** the plot point does not provide authoritative `location` or `involvedLocations`
- **WHEN** semantic-authority enrichment runs
- **THEN** title extraction SHALL preserve the existing destination-eligible behavior.
