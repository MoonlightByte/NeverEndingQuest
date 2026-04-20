## ADDED Requirements

### Requirement: Deterministic finale prerequisite repair SHALL clear live plot progression failures when uniquely provable

When a finale or conclusion beat is missing an explicit upstream gate and the immediate predecessor is uniquely provable from the authored sequence, remediation SHALL apply that prerequisite against the live module plot shape and verify that the validator no longer reports the same failure.

#### Scenario: Live list-shaped plot data accepts prerequisite repair

- **WHEN** `module_plot.json` stores `plotPoints` as a list of objects with `id` fields
- **AND** finale `PP018` has no prerequisites
- **AND** `PP017` is the uniquely provable immediate predecessor
- **THEN** remediation SHALL write `prerequisites: ["PP017"]` to the live finale node
- **AND** post-repair validation SHALL no longer emit the same missing-gate failure

#### Scenario: Ambiguous prerequisite remains fail-closed

- **WHEN** no unique upstream predecessor can be proven for a finale or conclusion beat
- **THEN** remediation SHALL NOT invent a prerequisite
- **AND** the residual result SHALL classify the blocker as ambiguous plot debt
