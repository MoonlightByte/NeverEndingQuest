## ADDED Requirements

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
