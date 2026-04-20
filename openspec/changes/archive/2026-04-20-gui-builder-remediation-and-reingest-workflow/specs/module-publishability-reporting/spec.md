# module-publishability-reporting Specification Delta

## ADDED Requirements

### Requirement: Reporting SHALL surface remediation classes for non-publishable outcomes
CLI and toolkit reporting SHALL expose remediation classes so operators can see whether a failure is caused by provenance, semantic blocking contradictions, warning-only semantic degradation, tooling debt, or real content remediation.

#### Scenario: Toolkit report includes remediation categories
- **GIVEN** a toolkit finishing run completes with mixed outcomes
- **WHEN** the toolkit report is written
- **THEN** the report SHALL include enough structured detail to distinguish remediation categories
- **AND** SHALL keep warning-only semantic degradation visible without collapsing it into generic failure text.
