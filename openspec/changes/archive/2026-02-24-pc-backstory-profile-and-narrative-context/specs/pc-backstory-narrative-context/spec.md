## ADDED Requirements

### Requirement: Character schema SHALL support a first-class backstory field
Character data SHALL include a top-level `backstory` string field that can be authored by players and consumed by narrative systems.

#### Scenario: Character includes authored backstory
- **WHEN** a PC is created or updated with backstory text
- **THEN** the value is persisted in character JSON as `backstory`

### Requirement: Portrait generation SHALL use bounded backstory context
Portrait prompt composition SHALL incorporate bounded/sanitized backstory context to improve narrative coherence of generated images.

#### Scenario: Portrait create with authored backstory
- **WHEN** portrait generation runs for a character with non-empty `backstory`
- **THEN** prompt composition includes concise backstory context alongside personality/appearance cues

### Requirement: Runtime narrative context SHALL expose backstory for flavor
Runtime character context formatting SHALL include bounded backstory hints so narration can reflect character history without affecting mechanics.

#### Scenario: DM/combat context generation
- **WHEN** runtime context builders format character identity blocks
- **THEN** bounded `backstory` text is available as narrative flavor input

### Requirement: NPC->PC promotion SHALL treat missing backstory as warning-first
Promotion workflows SHALL not fail solely due to missing backstory, but SHALL report profile-readiness warnings for follow-up completion.

#### Scenario: Promotion with missing backstory
- **WHEN** an NPC companion is promoted and `backstory` is blank
- **THEN** promotion apply succeeds and warning payload includes missing `backstory`

### Requirement: PDF Backstory field SHALL prefer authored backstory
PDF page 2 `Backstory` field population SHALL prioritize authored `character.backstory` content.

#### Scenario: Authored backstory exists
- **WHEN** PDF export runs for a character with non-empty `backstory`
- **THEN** page 2 `Backstory` field is populated from authored backstory (optionally followed by recent-adventure snippets)
