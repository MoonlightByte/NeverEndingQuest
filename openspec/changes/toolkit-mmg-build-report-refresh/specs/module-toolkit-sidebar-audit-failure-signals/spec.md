# module-toolkit-sidebar-audit-failure-signals Specification

## MODIFIED Requirements

### Requirement: Sidebar enrichment SHALL remain deterministic and additive

Sidebar enrichment SHALL reuse persisted report artifacts only and SHALL NOT run live audit scripts during module-list rendering.

#### Scenario: Module list request stays on existing data path

- **GIVEN** a request for the module sidebar list
- **WHEN** the backend enriches module entries with failure-state fields
- **THEN** it SHALL derive those fields from persisted report artifacts only
- **AND** it SHALL NOT invoke audit scripts or long-running validation flows
- **AND** it SHALL fail open if report parsing fails.

#### Scenario: Duplicate renderers stay aligned

- **GIVEN** the repository contains duplicate module-card renderers in `web/templates/module_toolkit.html` and `web/templates/module_builder.html`
- **WHEN** the new failure and handoff signals are implemented
- **THEN** both renderers SHALL support the same sidebar signaling behavior.

#### Scenario: MMG completion refreshes sidebar cards through persisted module-list data

- **GIVEN** a module whose sidebar card currently shows persisted media-debt failure text
- **AND** MMG successfully refreshes that module's persisted build report
- **WHEN** the GUI refreshes sidebar module-list data after MMG completion
- **THEN** both Module Builder and Module Toolkit card renderers SHALL consume the updated persisted report fields through the existing module-list path
- **AND** neither renderer SHALL recompute media debt directly from live MMG asset scan state.
