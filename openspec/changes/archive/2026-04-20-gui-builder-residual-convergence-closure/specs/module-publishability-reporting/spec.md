## ADDED Requirements

### Requirement: Reporting SHALL distinguish convergence instrumentation from residual closure progress

Toolkit and operations-facing report artifacts SHALL make it clear whether a run only classified residual blockers or actually reduced them.

#### Scenario: Residual closure canary persists advancement state

- **GIVEN** a residual-closure canary run for a module
- **WHEN** the canary report is written
- **THEN** it SHALL expose whether the module advanced beyond the previous residual blocker set
- **AND** SHALL include the current residual blocker classes and category counts

#### Scenario: Reporting distinguishes unresolved repair gap from author debt

- **WHEN** residual blockers remain after closure attempts
- **THEN** report surfaces SHALL distinguish between unresolved repair-engine coverage gaps and author/content debt where safe repair was not possible
