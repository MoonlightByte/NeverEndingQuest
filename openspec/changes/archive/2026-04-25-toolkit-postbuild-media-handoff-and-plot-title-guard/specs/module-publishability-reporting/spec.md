# module-publishability-reporting Specification Delta

## ADDED Requirements

### Requirement: Toolkit readiness reporting SHALL distinguish manual media handoff from structural build failure
When toolkit-source readiness receives gameplay failures caused only by structural monster media findings that are already classified as manual-only handoff debt, reporting SHALL preserve the debt explicitly without keeping readiness failed.

#### Scenario: Toolkit media-only gameplay debt no longer fails readiness
- **GIVEN** toolkit-source gameplay output contains blocking errors only for structural monster media debt
- **AND** each corresponding monster-media finding has outcome `provider_disabled_missing` or `attempted_but_unresolved`
- **AND** all non-gameplay readiness gates pass
- **WHEN** readiness reporting runs
- **THEN** `overall_status` SHALL be `pass`
- **AND** toolkit media policy metadata and manual remediation guidance SHALL remain present in the report.

#### Scenario: Mixed gameplay blockers still fail readiness
- **GIVEN** toolkit-source gameplay output contains at least one blocking error that is not explained by structural manual-only monster media debt
- **WHEN** readiness reporting runs
- **THEN** `overall_status` SHALL remain `fail`
- **AND** the report SHALL preserve the gameplay failure classification.
