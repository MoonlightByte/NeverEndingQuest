## Purpose

Define roster completeness and initiative visibility guarantees for party members in multi-PC combat encounters.

## Requirements

### Requirement: Multi-PC Encounter Creation SHALL Include Full Party Roster
In Multi-PC mode, encounter creation MUST include all `partyMembers` as player combatants.

#### Scenario: New encounter created during Multi-PC session
- **WHEN** `party_tracker.json` contains more than one party member and a new encounter is generated
- **THEN** each party member SHALL appear exactly once in `encounter.creatures` with `type: "player"`
- **AND** existing enemy and NPC creation behavior SHALL remain unchanged

#### Scenario: Single-player compatibility preserved
- **WHEN** only one party member is active
- **THEN** encounter creation SHALL remain behaviorally compatible with existing single-player flow
- **AND** no multi-player-only roster expansion SHALL be required

### Requirement: Combat Start SHALL Backfill Missing Player Combatants
Before turn processing, the system MUST normalize encounter roster completeness against `partyMembers`.

#### Scenario: Encounter file is missing a party member
- **WHEN** combat starts/resumes and one or more `partyMembers` are absent from `encounter.creatures`
- **THEN** missing players SHALL be injected from character-file state with additive defaults for missing optional fields
- **AND** existing encounter creatures (including enemy HP/status) SHALL remain unchanged

#### Scenario: Character data unavailable during backfill
- **WHEN** a missing party member cannot be loaded from character storage
- **THEN** combat startup SHALL fail open without process crash
- **AND** system diagnostics SHALL log a structured warning indicating which member could not be hydrated

### Requirement: Initiative Payload SHALL Not Hide Active Party Participants
Initiative data responses MUST include relevant player combatants while combat is active, including unconscious/incapacitated states.

#### Scenario: Unconscious player during active combat
- **WHEN** a player combatant has unconscious/incapacitated status and combat is still active
- **THEN** `initiative_data_response.combatants` SHALL include that player with status-consistent fields
- **AND** UI consumers SHALL not infer that the player is missing from combat roster

#### Scenario: Resolved combat has no valid combatants
- **WHEN** combat is no longer active or no combatants remain eligible for initiative display
- **THEN** initiative endpoint SHALL return inactive payload semantics without stale roster artifacts
