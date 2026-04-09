# module-publishability-reporting Specification

## Purpose
TBD - created by archiving change module-publication-publishable-gate. Update Purpose after archive.
## Requirements
### Requirement: CLI and toolkit reporting SHALL expose ready vs publishable clearly
Publication-facing reporting SHALL show both structural readiness and semantic publishability explicitly.

#### Scenario: CLI output includes both statuses
- **GIVEN** a publishability audit result
- **WHEN** CLI JSON or text output is emitted
- **THEN** it SHALL include explicit `ready_status` and `publishable_status` fields or equivalents

#### Scenario: Toolkit finisher report includes both statuses
- **GIVEN** a toolkit module finishing run
- **WHEN** the post-build report is written
- **THEN** the report SHALL expose whether the module is structurally ready and whether it is publishable

#### Scenario: Reporting does not collapse publishability into readiness
- **GIVEN** a module is ready but not publishable
- **WHEN** report surfaces are rendered
- **THEN** they SHALL NOT report a single ambiguous success state
- **AND** SHALL preserve the distinction clearly

