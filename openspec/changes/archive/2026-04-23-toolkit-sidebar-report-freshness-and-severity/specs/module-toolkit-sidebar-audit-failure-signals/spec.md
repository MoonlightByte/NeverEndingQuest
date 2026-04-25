## ADDED Requirements

### Requirement: Sidebar Failure Signals Require Authoritative Report Freshness

Persisted Module Builder sidebar failure signals SHALL only be derived from current authoritative `toolkit_build_report.json` artifacts.

#### Scenario: Current authoritative failed report produces compact failure text

- **GIVEN** `modules/<slug>/toolkit_build_report.json` exists
- **AND** `report_freshness.authoritative` is true
- **AND** `report_freshness.state` is `current`
- **AND** the report indicates failed readiness or publishability state
- **WHEN** the sidebar module list is derived
- **THEN** the sidebar SHALL emit the compact `brief_failure` mapping for the canonical blocker class

#### Scenario: Legacy failed report without freshness metadata fails open

- **GIVEN** `modules/<slug>/toolkit_build_report.json` exists
- **AND** the report indicates failed readiness or publishability state
- **AND** freshness metadata is absent or non-authoritative
- **WHEN** the sidebar module list is derived
- **THEN** the sidebar SHALL NOT emit `brief_failure`
- **AND** the sidebar SHALL NOT emit `media_generator_needed`

#### Scenario: Structural media handoff remains tied to structural debt

- **GIVEN** a current authoritative failed report
- **AND** the canonical remediation data indicates structural media debt
- **WHEN** the sidebar module list is derived
- **THEN** the sidebar SHALL emit `media_generator_needed`
- **AND** optional non-structural media warnings alone SHALL NOT create media handoff state
