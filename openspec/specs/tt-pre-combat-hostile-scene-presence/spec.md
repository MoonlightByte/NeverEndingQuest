## Purpose

Provide pre-combat situational awareness by exposing current-location hostile presences in the top UI strip before formal encounter creation, enabling players to see threats like bandit captains or corrupted spirits without initiating combat.

## Requirements

### Requirement: Pre-combat scene payload SHALL expose current-location hostiles separately from party actors

When no active encounter is controlling the top strip, the scene payload SHALL expose current-location hostile presences derived from location monster data as a separate collection from party members and party NPCs.

#### Scenario: Hostile visible before encounter creation
- **GIVEN** the current location includes a hostile in its scene roster
- **AND** no combat encounter has been created yet
- **WHEN** the client requests current party/scene data
- **THEN** the payload SHALL include the hostile under a hostile-scene collection
- **AND** SHALL NOT report the hostile as a party NPC or party member

### Requirement: Pre-combat hostile scene presence SHALL yield to active encounter state

Scene-hostile visibility SHALL not compete with formal encounter combatants once combat begins.

#### Scenario: Combat encounter replaces scene-hostile strip entries
- **WHEN** an active encounter exists for the same scene
- **THEN** the top strip SHALL use encounter-driven combatant presence as authoritative
- **AND** pre-combat hostile scene entries SHALL NOT duplicate the same actors beside combat entries

### Requirement: Hostile scene presence SHALL remain informational only

Pre-combat hostile scene visibility SHALL not itself create encounter state or party-membership state.

#### Scenario: Hostile visible without combat lock-in
- **WHEN** a hostile is present in the current scene before initiative starts
- **THEN** the pre-combat strip SHALL show the hostile as a hostile scene presence
- **AND** runtime SHALL NOT infer that combat has started solely from that visibility
