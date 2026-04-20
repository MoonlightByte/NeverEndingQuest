# module-semantic-publication-probes Specification Delta

## ADDED Requirements

### Requirement: Probe tooling debt SHALL be reported distinctly from authored semantic failures
Semantic publication probes SHALL distinguish missing or incomplete probe fixtures from authored module failures.

#### Scenario: Missing handoff fixture is tooling debt
- **GIVEN** a semantic probe cannot execute because a required fixture or harness input is absent
- **WHEN** the probe result is emitted
- **THEN** the result SHALL identify the issue as tooling debt or fixture absence
- **AND** SHALL keep it distinct from authored travel or NPC semantic failures.
