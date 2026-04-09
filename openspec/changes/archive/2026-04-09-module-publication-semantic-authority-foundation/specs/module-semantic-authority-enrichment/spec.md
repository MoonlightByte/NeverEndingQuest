## ADDED Requirements

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
