# toolkit-build-report-refresh-contract Specification

## ADDED Requirements

### Requirement: Toolkit build reports SHALL declare freshness state

Persisted `toolkit_build_report.json` artifacts SHALL include machine-readable freshness metadata so downstream consumers can distinguish a current authoritative report from a degraded or stale one.

#### Scenario: Toolkit finisher writes a current report

- **WHEN** a toolkit build completes its authoritative post-build finishing/reporting path
- **THEN** the system SHALL write `modules/<slug>/toolkit_build_report.json`
- **AND** the report SHALL include freshness metadata describing when it was written and which workflow produced it
- **AND** the freshness state SHALL indicate that the report reflects the latest known authoritative evaluation.

#### Scenario: Degraded report remains machine-readable

- **WHEN** a report-producing workflow completes with degraded-but-usable results
- **THEN** the persisted report SHALL still include freshness metadata
- **AND** the freshness state SHALL distinguish degraded reporting from a fully current report.

### Requirement: Publishability-affecting toolkit workflows SHALL refresh persisted reports explicitly

Toolkit remediation or revalidation workflows that recompute publishability-facing state SHALL refresh `toolkit_build_report.json` through an explicit report-refresh path rather than leaving the previous report implicitly authoritative.

#### Scenario: Revalidation refreshes persisted report after module fixes

- **GIVEN** a module whose persisted toolkit report no longer reflects the latest canonical module state
- **WHEN** an eligible toolkit remediation or revalidation workflow recomputes the module's publishability-facing outcome
- **THEN** that workflow SHALL rewrite `toolkit_build_report.json` through the shared refresh contract
- **AND** the rewritten report SHALL preserve current blocker classes and freshness metadata.

#### Scenario: Non-refresh workflows do not silently change sidebar truth

- **GIVEN** a workflow that does not run the explicit report-refresh contract
- **WHEN** that workflow changes module files or artifacts
- **THEN** it SHALL NOT rely on the sidebar to recompute live status
- **AND** the persisted report SHALL remain the only sidebar truth source until a valid refresh path runs.

### Requirement: Sidebar consumers SHALL remain persisted-report readers only

Sidebar and similar GUI consumers SHALL remain read-only consumers of persisted toolkit reports and SHALL NOT invoke live audits to repair or replace stale report state at read time.

#### Scenario: Sidebar consumes refreshed persisted report

- **GIVEN** a module card rendered from the existing module list path
- **WHEN** the sidebar needs build-status information
- **THEN** it SHALL read persisted report fields only
- **AND** it SHALL NOT invoke readiness, publishability, semantic, or gameplay audits during rendering.

#### Scenario: Missing or legacy report fails open

- **GIVEN** a module with no usable persisted toolkit report or with an older report shape
- **WHEN** a sidebar or report consumer reads the module status
- **THEN** the consumer SHALL fail open rather than crashing
- **AND** the refresh contract SHALL remain backward compatible with older reader behavior.

## Guidance

- Freshness metadata SHOULD identify the producing workflow, latest evaluation stage, and write timestamp.
- Report-refresh helpers SHOULD converge on one shared writer contract instead of duplicating JSON write logic across toolkit flows.
- This slice SHOULD remain a prerequisite for later `module-uploader-2` structural stabilization and SHOULD NOT absorb the broader uploader scope.
