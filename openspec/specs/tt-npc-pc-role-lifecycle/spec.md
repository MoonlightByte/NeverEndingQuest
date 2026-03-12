## Purpose

Define deterministic NPC -> PC promotion lifecycle behavior with identity continuity and party-state correctness.

## Requirements

### Requirement: Add Existing SHALL support promotable NPC companion candidates
Manage Party Add Existing SHALL provide a way to view promotable NPC companions and start explicit NPC -> PC promotion.

#### Scenario: Candidate list limited to party NPC companions
- **WHEN** DM selects NPC companion source mode in Add Existing
- **THEN** the list contains promotable entries derived from `party_tracker.partyNPCs` and excludes current `partyMembers`

#### Scenario: Existing player flow unchanged
- **WHEN** DM uses default player source mode
- **THEN** Add Existing behavior for player characters remains unchanged

### Requirement: NPC -> PC promotion SHALL preserve canonical identity and file continuity
Promotion SHALL update role in-place on the existing character record and SHALL NOT create duplicate files.

#### Scenario: In-place promotion
- **WHEN** DM confirms promotion of an NPC companion
- **THEN** the same character file is updated and reused as the promoted PC

#### Scenario: Character ID continuity
- **WHEN** promoted character lacks `character_id`
- **THEN** system generates and persists a stable `character_id` once

### Requirement: Promotion SHALL record lifecycle metadata in internal history
Promotion SHALL append an event to `_tabletop_role_history` with timestamp and role transition metadata.

#### Scenario: Lifecycle event appended
- **WHEN** promotion succeeds
- **THEN** `_tabletop_role_history` receives a new `promoted_to_pc` event with `from_role`, `to_role`, and source metadata

### Requirement: Promotion SHALL update party membership and role markers without auto-switch
Promotion SHALL move the character from NPC membership to PC membership and set role fields to player, while preserving current `active_character`.

#### Scenario: Membership transition without active switch
- **WHEN** promotion completes successfully
- **THEN** character is removed from `partyNPCs`, added to `partyMembers`, and `active_character` remains unchanged

#### Scenario: Role field normalization
- **WHEN** promotion applies
- **THEN** `type`, `character_type`, and `character_role` are set to player-consistent values

### Requirement: Promotion SHALL run post-transition validation and surface readiness warnings
Promotion SHALL execute shared audit/readiness checks after applying role changes and SHALL return warning context to DM UI.

#### Scenario: Promotion succeeds with readiness warnings
- **WHEN** character is mechanically valid but incomplete in narrative fields
- **THEN** promotion succeeds and response includes readiness warnings

#### Scenario: Promotion blocked on critical validation failure
- **WHEN** post-transition schema validation fails critically
- **THEN** promotion is rejected and no party membership change is committed

### Requirement: Promotion flow SHALL have no chat side effects
Promotion preview/apply SHALL execute via API and SHALL NOT enqueue narrative chat output.

#### Scenario: Silent promotion operations
- **WHEN** DM previews or confirms promotion
- **THEN** no user-facing chat message is emitted by the promotion workflow
