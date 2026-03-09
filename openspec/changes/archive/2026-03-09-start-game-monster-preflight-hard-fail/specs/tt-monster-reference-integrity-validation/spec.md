## MODIFIED Requirements

### Requirement: Module validation SHALL enforce monster reference integrity

The module validator SHALL fail validation when an area/location monster reference cannot be resolved to a monster stat file in the module, and its output SHALL be consumable by startup preflight remediation flow.

#### Scenario: Startup preflight consumes validator outcome deterministically

- **WHEN** validator reports unresolved references in `reference_integrity`
- **THEN** startup preflight SHALL treat that result as blocking unless remediated and revalidated
- **AND** startup decision logic SHALL rely on post-remediation validator output, not remediation attempt result alone

#### Scenario: Validator pass remains startup-compatible

- **WHEN** validator reports no unresolved references
- **THEN** startup preflight SHALL allow launch without remediation
- **AND** existing validation report semantics SHALL remain unchanged
