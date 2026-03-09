## ADDED Requirements

### Requirement: Module validation SHALL enforce monster reference integrity

The module validator SHALL fail validation when an area/location monster reference cannot be resolved to a monster stat file in the module, and its output SHALL remain consumable by startup preflight remediation flow.

#### Scenario: Unresolved monster reference fails validation

- **WHEN** an area/location references a monster name (for example `Cornfield Shadow`)
- **AND** `monsters/<normalized_name>.json` does not exist in the same module
- **THEN** validation SHALL mark `reference_integrity` as failed
- **AND** validation output SHALL include area/location context, source monster name, and expected file path

#### Scenario: Resolved reference passes validation

- **WHEN** all area/location monster references map to existing `monsters/*.json` files
- **THEN** `reference_integrity` SHALL pass
- **AND** no unresolved-reference errors SHALL be emitted

#### Scenario: Startup preflight consumes validator outcome deterministically

- **WHEN** validator reports unresolved references in `reference_integrity`
- **THEN** startup preflight SHALL treat that result as blocking unless remediated and revalidated
- **AND** startup decision logic SHALL rely on post-remediation validator output, not remediation attempt result alone

#### Scenario: Validator pass remains startup-compatible

- **WHEN** validator reports no unresolved references
- **THEN** startup preflight SHALL allow launch without remediation
- **AND** existing validation report semantics SHALL remain unchanged

#### Scenario: Normalization is deterministic

- **WHEN** a monster reference includes mixed case, spaces, or apostrophes
- **THEN** validator normalization SHALL produce the same slug convention used by combat monster lookup
- **AND** existing correctly named monster files SHALL resolve without false failures
