## ADDED Requirements

### Requirement: Residual readiness closure SHALL target validator-derived unresolved blocker sets

After convergence instrumentation classifies residual readiness blockers, the toolkit readiness workflow SHALL attempt deterministic closure against the validator-derived unresolved set rather than retrying generic repair passes.

#### Scenario: Validator-derived monster reference set drives closure

- **WHEN** readiness validation reports unresolved monster references with expected file paths
- **THEN** residual closure SHALL derive closure targets from those validator outputs
- **AND** SHALL attempt deterministic materialization or reuse against that derived set before final classification

#### Scenario: Residual closure stops at irreducible debt

- **WHEN** residual closure cannot safely resolve the validator-derived blocker set
- **THEN** the workflow SHALL stop and classify the remaining blockers explicitly
- **AND** SHALL NOT increase retry count as a substitute for missing deterministic coverage

### Requirement: Numillian SHALL remain the primary residual-closure canary

The toolkit workflow SHALL use `The_Hidden_City_of_Numillian` as the primary regression canary for residual convergence closure.

#### Scenario: Canary artifact proves advancement or clean residual debt

- **WHEN** the residual-closure canary runs
- **THEN** the persisted artifact SHALL state whether the module advanced beyond the previous residual blocker set
- **AND** any remaining failures SHALL be classifiable as unresolved repair-engine gap or explicit author/content debt
