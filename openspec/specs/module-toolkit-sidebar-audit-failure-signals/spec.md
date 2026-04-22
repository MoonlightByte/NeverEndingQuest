# module-toolkit-sidebar-audit-failure-signals Specification

## Purpose
TBD - created by archiving change gui-builder-sidebar-audit-failure-signals. Update Purpose after archive.
## Requirements
### Requirement: Sidebar module cards SHALL surface brief persisted build failures

The GUI Module Builder sidebar SHALL be able to render a short build-failure message for a world-registry module card when a persisted toolkit build report indicates the module is not ready or not publishable.

#### Scenario: Failed module renders a concise failure line

- **GIVEN** a module entry returned by the existing module-list path
- **AND** `modules/<slug>/toolkit_build_report.json` exists and indicates failed readiness or publishability state
- **WHEN** the sidebar renders the module card
- **THEN** the card SHALL include a brief user-facing failure line
- **AND** the line SHALL be visually distinct as a failure signal
- **AND** the existing module card metadata and click behavior SHALL remain intact

#### Scenario: Missing report fails open

- **GIVEN** a module entry returned by the existing module-list path
- **AND** no usable persisted toolkit build report exists for that module
- **WHEN** the sidebar renders the module card
- **THEN** the card SHALL render without the new failure line
- **AND** the module list request SHALL NOT fail because of the missing report

### Requirement: Sidebar media handoff SHALL reflect persisted manual media debt

The sidebar SHALL surface a short manual handoff indicator when the persisted build report shows the module still requires manual `Module Media Generator` work.

#### Scenario: Media-required module shows handoff indicator

- **GIVEN** a module entry whose persisted toolkit build report indicates structural media debt or toolkit manual media generation requirement
- **WHEN** the sidebar renders the module card
- **THEN** the card SHALL include a short secondary handoff line indicating that `Module Media Generator` is needed
- **AND** the handoff line SHALL be secondary to the primary failure line

#### Scenario: Non-media failure does not show media handoff

- **GIVEN** a module entry whose persisted toolkit build report indicates failure without manual media-generation debt
- **WHEN** the sidebar renders the module card
- **THEN** the card SHALL NOT show the media handoff line

### Requirement: Sidebar enrichment SHALL remain deterministic and additive

Sidebar enrichment SHALL reuse persisted report artifacts only and SHALL NOT run live audit scripts during module-list rendering.

#### Scenario: Module list request stays on existing data path

- **GIVEN** a request for the module sidebar list
- **WHEN** the backend enriches module entries with failure-state fields
- **THEN** it SHALL derive those fields from persisted report artifacts only
- **AND** it SHALL NOT invoke audit scripts or long-running validation flows
- **AND** it SHALL fail open if report parsing fails

#### Scenario: Duplicate renderers stay aligned

- **GIVEN** the repository contains duplicate module-card renderers in `web/templates/module_toolkit.html` and `web/templates/module_builder.html`
- **WHEN** the new failure and handoff signals are implemented
- **THEN** both renderers SHALL support the same sidebar signaling behavior

