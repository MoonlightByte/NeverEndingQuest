# tt-inventory-possession-authority Specification

## Purpose
TBD - created by archiving change tt-authoritative-transition-inventory-runtime-reset. Update Purpose after archive.
## Requirements
### Requirement: Tracked item possession SHALL resolve from committed Python state
The system SHALL answer tracked item possession questions from committed character state rather than from narration memory or recap prose.

#### Scenario: Possession query returns committed inventory truth
- **WHEN** a player asks whether a tracked item is still in a character's pack or inventory
- **THEN** runtime SHALL resolve the answer from committed character state for that character

#### Scenario: Narration memory cannot override committed possession
- **WHEN** prior narration conflicts with committed character inventory state
- **THEN** committed character inventory state SHALL win for possession truth

### Requirement: Party-to-party tracked item transfers SHALL be transactional
Explicit transfer of a tracked item between characters SHALL either persist both sides of the transfer or persist neither side.

#### Scenario: Transfer commits both giver removal and receiver add
- **WHEN** runtime accepts an explicit tracked item transfer from one character to another
- **THEN** runtime SHALL persist the giver-side removal and receiver-side add as one successful logical commit

#### Scenario: Partial transfer persistence is rejected
- **WHEN** runtime cannot persist one side of an explicit tracked item transfer
- **THEN** runtime SHALL reject the transfer outcome as a failed state mutation rather than leaving only one side committed

### Requirement: Possession contradiction turns SHALL not bypass authoritative checks as narration-only
Turns that explicitly challenge tracked item possession SHALL not finalize through low-risk narration-only routing before authoritative inventory checks run.

#### Scenario: Missing-item contradiction forces authoritative inventory check
- **WHEN** a player says a tracked item is missing or asks where it went
- **THEN** runtime SHALL run authoritative possession handling before the turn can be treated as narration-only

### Requirement: Multi-PC inventory grounding SHALL use active-character identity
In tabletop mode, inventory-aware DM context for a turn SHALL ground on the active character unless the turn explicitly targets a different named character.

#### Scenario: Active PC inventory context is used in multiplayer mode
- **WHEN** the active character is not the first entry in `partyMembers`
- **THEN** inventory-aware runtime context for that turn SHALL use the active character's committed inventory state

