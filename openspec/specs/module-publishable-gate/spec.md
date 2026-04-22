# module-publishable-gate Specification

## Purpose
TBD - created by archiving change module-publication-publishable-gate. Update Purpose after archive.
## Requirements
### Requirement: The repo SHALL distinguish readiness from publishability
The final publication gate SHALL expose `ready` and `publishable` as distinct states so structural validity and release safety are not conflated.

#### Scenario: Ready but not publishable remains distinguishable
- **GIVEN** a module passes structural readiness gates
- **AND** fails semantic publication audit or semantic probe checks
- **WHEN** the standalone publishability audit runs
- **THEN** the output SHALL report `ready_status=pass`
- **AND** `publishable_status=fail`

#### Scenario: Publishable requires all release-facing gates to pass
- **GIVEN** a module passes readiness, semantic publication audit, and semantic probe checks
- **WHEN** the standalone publishability audit runs
- **THEN** the output SHALL report `publishable_status=pass`
- **AND** return success exit code

#### Scenario: Publishability exit code follows the stricter release decision
- **GIVEN** a module is not publishable
- **WHEN** the standalone publishability audit runs
- **THEN** the command SHALL return a failing exit code even if readiness passed

### Requirement: Publishability output SHALL preserve explicit debt classes for structurally valid toolkit modules
Publishability reporting SHALL preserve explicit residual debt classes when a toolkit-built module is structurally valid but still blocked by release-facing media debt or explicitly deferred semantic ambiguity debt.

#### Scenario: Structurally valid toolkit module remains not publishable for explicit residual debt
- **GIVEN** a toolkit-built module passes structural validation and readiness checks required for its declared source
- **AND** publishability still fails because combat-valid monster base media is missing or a semantic issue is explicitly classified as deferred Phase 2 ambiguity debt
- **WHEN** publishability output is emitted
- **THEN** the report SHALL preserve those residual debt classes explicitly
- **AND** SHALL keep the result distinguishable from structural readiness failure

### Requirement: Publishability SHALL fail on semantic blocking findings, not warning-only semantic degradation
The publishable gate SHALL fail when semantic publication layers produce blocking findings, but warning-only or tooling-debt degradation alone SHALL NOT be treated as an equivalent hard semantic blocker.

#### Scenario: Ready module with warning-only semantic degradation remains distinguishable from blocking semantic failure
- **GIVEN** readiness passes
- **AND** semantic publication layers report warnings or tooling debt only
- **AND** no semantic blocking findings are present
- **WHEN** the publishable gate computes final status
- **THEN** it SHALL preserve a status distinct from blocking semantic failure
- **AND** SHALL NOT report the module as blocked by semantic contradiction.

### Requirement: Publishability SHALL NOT treat shared static fallback media as module-local fulfillment

Shared runtime fallback media under `web/static/media/{npcs,monsters}` MUST NOT satisfy module-local media requirements for publication readiness.

#### Scenario: Shared fallback exists but module-local media is missing
- **GIVEN** a module is missing required media under `modules/<module>/media`
- **AND** a matching asset exists under `web/static/media/npcs` or `web/static/media/monsters`
- **WHEN** publishability is evaluated
- **THEN** the module SHALL remain blocked for missing module-local media
- **AND** the shared static fallback asset SHALL NOT be treated as resolving that debt

