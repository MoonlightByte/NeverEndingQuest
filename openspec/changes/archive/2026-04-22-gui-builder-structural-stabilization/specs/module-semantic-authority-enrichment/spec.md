## ADDED Requirements

### Requirement: Canonical destination authority SHALL exclude evocative prose-only phrases
Semantic-authority enrichment MUST derive canonical destination authority from canonical identity evidence and MUST NOT promote freeform evocative prose into destination authority without a strong canonical anchor.

#### Scenario: Canonical location fields produce destination authority
- **WHEN** semantic-authority enrichment reads `location.name`, `location.aliases`, or `location.source_room_title`
- **THEN** it MUST allow those values to contribute canonical destination authority records

#### Scenario: Evocative prose does not become canonical destination authority
- **WHEN** semantic-authority enrichment encounters phrases such as `find sanctuary`, `next hall`, or other descriptive prose in freeform narrative fields without a canonical alias anchor
- **THEN** it MUST NOT emit those phrases as canonical destination authority records
- **AND** MAY record them as non-blocking diagnostics instead

#### Scenario: Strong travel phrasing still requires canonical anchor
- **WHEN** semantic-authority enrichment sees strong travel wording in prose
- **THEN** it MUST only emit canonical destination authority if the phrase resolves through a canonical location alias or identity field
- **AND** otherwise MUST leave the phrase outside canonical destination authority

### Requirement: Visible NPC authority SHALL satisfy baseline scene authority
Semantic-authority enrichment MUST treat visibly authored NPC authority as sufficient baseline scene authority and reserve reveal bindings for hidden or reveal-only authored cases.

#### Scenario: Visible NPC passes without reveal binding
- **WHEN** an NPC has valid `visible_location_ids`
- **THEN** semantic-authority enrichment MUST emit the NPC as scene-authoritative
- **AND** MUST NOT require reveal bindings for that NPC to satisfy baseline authority

#### Scenario: Hidden or reveal-only NPC still requires reveal authority
- **WHEN** an NPC lacks visible location authority but is authored as hidden or reveal-only
- **THEN** semantic-authority enrichment MUST require reveal bindings or equivalent hidden-authority evidence
- **AND** MUST emit a missing-authority diagnostic if that evidence is absent
