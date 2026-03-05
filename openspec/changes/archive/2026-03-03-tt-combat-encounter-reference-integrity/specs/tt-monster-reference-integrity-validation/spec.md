## ADDED Requirements

### Requirement: Module validation SHALL enforce monster reference integrity

The module validator SHALL fail validation when an area/location monster reference cannot be resolved to a monster stat file in the module.

#### Scenario: Unresolved monster reference fails validation

- **WHEN** an area/location references a monster name (for example `Cornfield Shadow`)
- **AND** `monsters/<normalized_name>.json` does not exist in the same module
- **THEN** validation SHALL mark `reference_integrity` as failed
- **AND** validation output SHALL include area/location context, source monster name, and expected file path

#### Scenario: Resolved reference passes validation

- **WHEN** all area/location monster references map to existing `monsters/*.json` files
- **THEN** `reference_integrity` SHALL pass
- **AND** no unresolved-reference errors SHALL be emitted

#### Scenario: Normalization is deterministic

- **WHEN** a monster reference includes mixed case, spaces, or apostrophes
- **THEN** validator normalization SHALL produce the same slug convention used by combat monster lookup
- **AND** existing correctly named monster files SHALL resolve without false failures
