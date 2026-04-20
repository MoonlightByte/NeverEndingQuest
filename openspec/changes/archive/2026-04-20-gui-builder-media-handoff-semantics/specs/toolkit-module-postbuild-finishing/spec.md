# toolkit-module-postbuild-finishing Specification Delta

## ADDED Requirements

### Requirement: Toolkit finisher SHALL distinguish media-only debt from build failure
Toolkit finishing SHALL not report an overall failed build when structural build stages are green and the only remaining issue is missing module monster or NPC media that must be generated manually.

#### Scenario: Toolkit build completes with explicit media handoff
- **GIVEN** a toolkit finishing run has completed structural stages successfully
- **AND** required module-local monster or NPC media is still missing
- **AND** manual media generation remains the intended workflow
- **WHEN** the finisher emits its result payload and report
- **THEN** it SHALL report a successful build outcome with explicit post-build media handoff semantics
- **AND** SHALL preserve the missing media debt details
- **AND** SHALL direct the operator to `Module Builder -> Module Media Generator`

#### Scenario: Structural failures still fail
- **GIVEN** a toolkit finishing run has a real structural or finishing failure unrelated to media-only handoff debt
- **WHEN** the finisher emits its result payload and report
- **THEN** it SHALL preserve failed build semantics
- **AND** SHALL NOT reinterpret that outcome as success-with-handoff
