## ADDED Requirements

### Requirement: Residual monster reference closure SHALL preserve validator-target identity

Validator-driven monster closure SHALL preserve the exact unresolved target identity surfaced by `reference_integrity` so remediation and reporting remain tied to the file path the validator expects.

#### Scenario: Expected file path remains visible in residual reporting

- **WHEN** `reference_integrity` reports an unresolved monster reference with an expected file path
- **THEN** residual reporting SHALL preserve that expected slug/path in the closure result
- **AND** unresolved outcomes SHALL remain attributable to the validator-targeted file rather than only the authored monster display name
