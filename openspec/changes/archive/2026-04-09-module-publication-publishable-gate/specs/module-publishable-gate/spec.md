## ADDED Requirements

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
