# tt-location-reconciler-history-hygiene Specification

## Purpose
TBD - created by archiving change tt-runtime-context-hygiene-stabilization. Update Purpose after archive.
## Requirements
### Requirement: Location reconciler SHALL consume same-location authoritative evidence only
Location reconciliation SHALL restrict its evidence set to current-scene authoritative inputs and same-location derived memory with matching provenance.

#### Scenario: Reconciler runs for current location
- **WHEN** the reconciler evaluates hostile or scene state for a target location
- **THEN** it SHALL use the current location packet, current module state, and same-location raw conversation turns as authoritative evidence
- **AND** it SHALL ignore derived location summaries or chronicles whose provenance does not match the target location

#### Scenario: Mislabeled summary block exists in preserved history
- **WHEN** preserved history contains a derived summary block whose visible text or legacy header conflicts with the target location
- **AND** the block lacks matching provenance for the reconciliation target
- **THEN** the reconciler SHALL exclude that block from the model input
- **AND** reconciliation output SHALL not be based on that mismatched summary

### Requirement: Reconciler SHALL preserve current hostile state when evidence is mismatched or insufficient
If same-location authoritative evidence is insufficient, the reconciler SHALL fail safe rather than mutating the current location's hostile roster from mismatched history.

#### Scenario: Insufficient same-location evidence
- **WHEN** the reconciler cannot assemble enough same-location authoritative evidence to justify a state change
- **THEN** it SHALL preserve the current hostile roster unchanged
- **AND** it SHALL record that reconciliation degraded rather than applying a speculative mutation

