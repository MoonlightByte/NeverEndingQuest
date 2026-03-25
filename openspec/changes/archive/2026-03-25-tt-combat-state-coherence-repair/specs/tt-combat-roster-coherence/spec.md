## MODIFIED Requirements

### Requirement: Combat Start SHALL Backfill Missing Player Combatants
Before turn processing, the system MUST normalize encounter roster completeness against canonical `partyMembers` identity and MUST dedupe mixed-form player labels before injecting or advertising player combatants.

#### Scenario: Encounter file is missing a party member
- **WHEN** combat starts or resumes and one or more canonical `partyMembers` are absent from `encounter.creatures`
- **THEN** missing players SHALL be injected from character-file state with additive defaults for missing optional fields
- **AND** existing encounter creatures (including enemy HP and status) SHALL remain unchanged

#### Scenario: Mixed-form party labels are present at combat start
- **WHEN** combat startup receives party entries that normalize to the same canonical identity (for example `xorn` and `Xorn`)
- **THEN** runtime SHALL create exactly one logical player combatant for that canonical party member
- **AND** prompt state, initiative summaries, and encounter hydration SHALL not expose duplicate player identities for the same PC

#### Scenario: Character data unavailable during backfill
- **WHEN** a missing party member cannot be loaded from character storage
- **THEN** combat startup SHALL fail open without process crash
- **AND** system diagnostics SHALL log a structured warning indicating which member could not be hydrated

## ADDED Requirements

### Requirement: Player Combat Targeting SHALL Prefer Living Canonical Targets
Local combat command resolution MUST prefer living canonical target matches and MUST reject already-defeated matches when a living target of the same canonical family remains available.

#### Scenario: Partial target name matches both dead and living enemies
- **WHEN** a player combat command uses a partial target string that matches a dead enemy and a living enemy of the same canonical identity
- **THEN** runtime SHALL resolve the command to the living enemy
- **AND** the command SHALL NOT reuse the dead enemy as the selected target

#### Scenario: Partial target name matches only defeated enemies
- **WHEN** a player combat command resolves only to enemies whose state is dead, unconscious, or defeated
- **THEN** runtime SHALL reject the target as no longer valid
- **AND** the command SHALL NOT queue damage, narration, or prompt follow-up as though a living target was hit
