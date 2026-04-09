## ADDED Requirements

### Requirement: Semantic publication probes SHALL validate authored interaction semantics deterministically
Publication-time semantic probe execution SHALL validate authored travel, escort/handoff, and hidden/revealable NPC discovery semantics using deterministic fixtures and expected targets.

#### Scenario: Travel probe validates canonical destination target
- **GIVEN** a travel probe fixture derived from authored destination semantics
- **WHEN** the semantic probe harness executes the travel probe
- **THEN** the probe SHALL resolve to the canonical expected location id or fail with an explicit semantic failure class

#### Scenario: Escort or handoff probe validates continuity target
- **GIVEN** an escort or handoff probe fixture derived from authored continuity semantics
- **WHEN** the semantic probe harness executes the probe
- **THEN** the probe SHALL validate the expected continuity target or fail with an explicit probe result

#### Scenario: Hidden or revealable NPC probe validates discovery authority
- **GIVEN** a hidden or revealable NPC probe fixture derived from authored discovery semantics
- **WHEN** the semantic probe harness executes the probe
- **THEN** the probe SHALL validate the expected NPC discovery path or fail with an explicit semantic failure class

#### Scenario: Probe harness remains standalone before publishable gate rollout
- **GIVEN** the semantic probe harness returns failing probes
- **WHEN** this phase is implemented before the final publishable-gate slice
- **THEN** the harness SHALL remain a standalone report surface
- **AND** SHALL NOT by itself redefine repo-wide release policy
