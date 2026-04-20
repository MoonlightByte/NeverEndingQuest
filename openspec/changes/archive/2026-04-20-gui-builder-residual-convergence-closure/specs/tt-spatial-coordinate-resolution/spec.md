## ADDED Requirements

### Requirement: Residual spatial contradictions SHALL either converge or escalate explicitly

When shared spatial remediation is re-run during residual closure, unchanged contradiction sets SHALL be escalated as author-required structural debt instead of being retried implicitly.

#### Scenario: Spatial remediation resolves contradiction set

- **WHEN** residual closure re-runs shared spatial remediation for a module with adjacency contradictions
- **AND** the contradiction set is reduced or eliminated
- **THEN** reporting SHALL record that spatial closure advanced

#### Scenario: Spatial contradiction set remains unchanged

- **WHEN** residual closure re-runs shared spatial remediation
- **AND** the contradiction set after remediation is unchanged
- **THEN** reporting SHALL classify the result as unresolved structural spatial debt
- **AND** the workflow SHALL stop rather than retrying equivalent remediation again
