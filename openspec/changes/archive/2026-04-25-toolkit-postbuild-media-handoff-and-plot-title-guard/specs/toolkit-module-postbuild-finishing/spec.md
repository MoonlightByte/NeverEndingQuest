# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit finisher SHALL preserve media handoff after readiness relaxation
When toolkit-source readiness stops failing because the remaining gameplay debt is manual-only structural monster media debt, toolkit finishing SHALL preserve explicit media handoff guidance rather than collapsing the module into generic success.

#### Scenario: Media handoff remains explicit after toolkit readiness passes
- **GIVEN** a toolkit build is structurally valid
- **AND** readiness now passes because the only gameplay blockers were manual-only structural monster media findings
- **WHEN** toolkit finishing or publication-facing reporting is emitted
- **THEN** the report SHALL still include the structural media debt summary
- **AND** SHALL name the manual monster-media generation workflow as the next remediation step.
