# toolkit-module-remediation-workflow Specification

## Purpose
TBD - created by archiving change gui-builder-remediation-and-reingest-workflow. Update Purpose after archive.
## Requirements
### Requirement: Toolkit remediation workflow SHALL classify post-build failures into deterministic action buckets
Toolkit post-build reporting SHALL classify failures into deterministic remediation buckets so operators can distinguish infrastructure/order bugs, provenance gaps, warning-only semantic debt, and real content blockers.

#### Scenario: Structured monster media debt is surfaced as content remediation
- **GIVEN** a toolkit-built module declares real structured monsters
- **AND** required monster media assets are missing
- **WHEN** remediation reporting is generated
- **THEN** the workflow SHALL classify the outcome as content remediation
- **AND** SHALL NOT collapse it into a generic finisher failure.

#### Scenario: Legacy toolkit provenance absence is surfaced distinctly
- **GIVEN** a module was not produced by the toolkit path
- **WHEN** it is audited with `source="toolkit"`
- **THEN** the workflow SHALL classify the result as a toolkit provenance gap
- **AND** SHALL recommend rebuild or migration rather than implying generic audit corruption.

### Requirement: Numillian SHALL be the first toolkit canary for remediation workflow validation
The remediation workflow SHALL use `The_Hidden_City_of_Numillian` as the first toolkit canary because it exercises toolkit provenance, semantic warning handling, and real monster-media debt in one flow.

#### Scenario: Numillian canary rerun produces categorized outcomes
- **GIVEN** the remediation workflow is implemented
- **WHEN** `The_Hidden_City_of_Numillian` is rerun through the toolkit flow
- **THEN** the resulting report SHALL distinguish provenance, semantic, and media blocker classes explicitly.

