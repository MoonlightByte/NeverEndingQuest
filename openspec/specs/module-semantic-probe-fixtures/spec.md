# module-semantic-probe-fixtures Specification

## Purpose
TBD - created by archiving change module-publication-live-play-probes. Update Purpose after archive.
## Requirements
### Requirement: Probe fixtures SHALL be source-driven and reviewable
Semantic publication probe fixtures SHALL encode player-like interactions, expected canonical targets, and expected failure classes in a deterministic, reviewable form.

#### Scenario: Fixture captures player-facing travel phrase and expected destination
- **GIVEN** a travel fixture
- **WHEN** the fixture is serialized for probe execution
- **THEN** it SHALL include a player-like phrase or authored destination reference, canonical expected target, and source provenance

#### Scenario: Fixture captures escort or handoff expectation
- **GIVEN** an escort or handoff fixture
- **WHEN** the fixture is serialized for probe execution
- **THEN** it SHALL include the expected continuity target and enough source context to explain the expectation deterministically

#### Scenario: Fixture captures hidden or revealable NPC expectation
- **GIVEN** a hidden or revealable NPC discovery fixture
- **WHEN** the fixture is serialized for probe execution
- **THEN** it SHALL include the canonical NPC identity, expected discovery context, and source provenance

#### Scenario: Weak fixture derivation can degrade without hard-failing unrelated probes
- **GIVEN** a module lacks enough source evidence to derive one complete fixture
- **WHEN** the harness prepares fixtures
- **THEN** the affected probe preparation MAY degrade with a warning
- **AND** unrelated valid probes SHALL still execute deterministically

