# tt-narrator-scene-context-hygiene Specification

## Purpose
TBD - created by archiving change narrator-scene-context-hygiene-and-failclosed-ux. Update Purpose after archive.
## Requirements
### Requirement: Live narrator payload SHALL exclude historical location summaries and chronicles

Outbound payload assembly for the live narrator SHALL omit assistant historical location-summary and location-chronicle blocks from prior scenes.

#### Scenario: Historical location summaries exist in retained conversation history
- **GIVEN** canonical conversation history still contains prior `=== LOCATION SUMMARY ===` or `=== LOCATION CHRONICLE ===` assistant messages
- **WHEN** the runtime assembles the outbound payload for the main narrator turn
- **THEN** those historical summary/chronicle messages SHALL be excluded from the live narrator payload
- **AND** recent raw scene turns SHALL remain present

### Requirement: Live narrator payload SHALL exclude full remote-location atlas context

Outbound payload assembly for the live narrator SHALL omit the full module world atlas system message when preparing a live scene turn.

#### Scenario: Full atlas and current location packet both exist
- **GIVEN** outbound context contains both `=== COMPLETE MODULE WORLD ATLAS ===` and `Current Location:` system messages
- **WHEN** the runtime assembles the live narrator payload
- **THEN** the atlas message SHALL be excluded
- **AND** the current location packet SHALL remain present

### Requirement: Live narrator payload SHALL compact completed plot history

Outbound payload assembly for the live narrator SHALL preserve active and upcoming plot pressure while suppressing verbose completed-plot prose.

#### Scenario: Plot packet contains completed, active, and upcoming sections
- **GIVEN** the outbound plot packet contains completed, active, and upcoming plot content
- **WHEN** the runtime assembles the live narrator payload
- **THEN** active and upcoming plot context SHALL remain available to the narrator
- **AND** verbose completed-beat prose SHALL be omitted or replaced with compact summary text

### Requirement: Narrator-only sanitation SHALL preserve canonical history and validator inputs

Scene-context hygiene for the narrator SHALL be applied only to the live narrator payload and SHALL NOT rewrite canonical conversation history or validator-local context assembly.

#### Scenario: Narrator sanitation runs for one live turn
- **WHEN** narrator payload sanitation excludes historical summaries, atlas content, or verbose completed-plot prose
- **THEN** canonical stored conversation history SHALL remain unchanged
- **AND** validator fail-closed behavior for deterministic scene/state checks SHALL remain unchanged

