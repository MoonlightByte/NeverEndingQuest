# module-semantic-publication-probes Specification

## Purpose
TBD - created by archiving change module-publication-live-play-probes. Update Purpose after archive.
## Requirements
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

### Requirement: Probe tooling debt SHALL be reported distinctly from authored semantic failures
Semantic publication probes SHALL distinguish missing or incomplete probe fixtures from authored module failures.

#### Scenario: Missing handoff fixture is tooling debt
- **GIVEN** a semantic probe cannot execute because a required fixture or harness input is absent
- **WHEN** the probe result is emitted
- **THEN** the result SHALL identify the issue as tooling debt or fixture absence
- **AND** SHALL keep it distinct from authored travel or NPC semantic failures.

### Requirement: Travel probes SHALL derive only from canonical destination authority
Semantic publication travel probes MUST be generated from canonical destination authority records and MUST NOT treat evocative prose-only phrases as standalone travel fixtures.

#### Scenario: Canonical destination phrase becomes travel probe
- **WHEN** the probe harness receives a destination phrase backed by canonical location identity evidence
- **THEN** it MUST derive a travel probe for that phrase
- **AND** the probe MUST target the expected canonical location id

#### Scenario: Evocative prose phrase is excluded from travel probes
- **WHEN** the probe harness encounters a prose-derived phrase without canonical destination authority
- **THEN** it MUST NOT derive a blocking travel probe from that phrase
- **AND** MUST preserve probe failures for real canonical travel mismatches only

### Requirement: NPC publication probes SHALL distinguish visible and hidden authority
Semantic publication probes MUST treat visible NPC authority and hidden/reveal authority as distinct validation paths.

#### Scenario: Visible NPC does not fail hidden-authority probe
- **WHEN** an NPC has valid visible scene authority
- **THEN** publication probing MUST NOT emit `hidden_npc_missing_authority` for that NPC solely because reveal bindings are absent

#### Scenario: Hidden NPC without visible or reveal authority fails
- **WHEN** an NPC is authored as hidden or revealable and has neither visible authority nor reveal authority
- **THEN** publication probing MUST fail with an explicit hidden-authority semantic failure

