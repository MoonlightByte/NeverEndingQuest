# module-semantic-authority-enrichment Specification

## Purpose
TBD - created by archiving change module-publication-semantic-authority-foundation. Update Purpose after archive.
## Requirements
### Requirement: Module publication flows SHALL emit a shared semantic-authority payload
Ingest and toolkit-finishing flows SHALL emit one additive semantic-authority payload that captures deterministic destination and NPC authority semantics for later publication auditing.

#### Scenario: Shared enrichment contract across ingest and toolkit finishing
- **GIVEN** a module has authored locations, aliases, plot references, or scene NPC records
- **WHEN** semantic-authority enrichment runs through ingest or toolkit finishing
- **THEN** both flows SHALL emit the same normalized payload shape for location aliases, destination phrases, and NPC scene authority
- **AND** SHALL NOT maintain separate incompatible enrichment formats

#### Scenario: Destination phrases carry provenance and normalized targets
- **GIVEN** authored module content contains named destinations or room-reference phrases
- **WHEN** semantic-authority enrichment resolves those phrases
- **THEN** each emitted phrase record SHALL include a normalized phrase key, canonical target location id or candidate ids, and source provenance

#### Scenario: Visible and revealable NPCs carry scene-authority records
- **GIVEN** a module authors NPCs that are visible in-scene or discoverable through revealable hooks
- **WHEN** semantic-authority enrichment runs
- **THEN** the payload SHALL emit NPC scene-authority records that identify canonical NPC names, visible location ids or reveal bindings, and source provenance

#### Scenario: Weak or ambiguous source prose fails open inside enrichment
- **GIVEN** destination or NPC source prose is incomplete or ambiguous
- **WHEN** semantic-authority enrichment cannot resolve one unique authority record
- **THEN** enrichment SHALL record ambiguity or missing-authority diagnostics
- **AND** SHALL fail open rather than hard-crashing ingest or toolkit finishing

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

### Requirement: Semantic authority SHALL normalize uniquely anchored short-form destination phrases
When a player-facing destination phrase remains unresolved, semantic-authority enrichment SHALL collapse it to canonical destination authority only when one already-resolved authored alias in the same module provides a deterministic unique anchor.

#### Scenario: Short-form destination collapses to one resolved authored alias
- **GIVEN** semantic-authority enrichment has already resolved `silent oath chamber` to location `H03`
- **AND** the same module still contains unresolved player-facing phrase `oath chamber`
- **WHEN** short-form destination normalization runs
- **THEN** the phrase SHALL collapse to `H03`
- **AND** the payload SHALL preserve that the collapse was derived from the resolved authored alias rather than direct authored identity.

#### Scenario: Short-form destination remains unresolved when anchor is ambiguous
- **GIVEN** a module contains two already-resolved authored aliases that both plausibly match the same unresolved short-form phrase
- **WHEN** short-form destination normalization runs
- **THEN** the phrase SHALL remain unresolved
- **AND** SHALL preserve ambiguity diagnostics rather than forcing one canonical destination.

#### Scenario: Prose-only phrase without resolved anchor remains outside canonical authority
- **GIVEN** an unresolved player-facing phrase has no already-resolved authored alias that provides a deterministic anchor
- **WHEN** short-form destination normalization runs
- **THEN** enrichment SHALL NOT promote that phrase into canonical destination authority
- **AND** MAY preserve it as unresolved or diagnostic output according to existing enrichment rules.

