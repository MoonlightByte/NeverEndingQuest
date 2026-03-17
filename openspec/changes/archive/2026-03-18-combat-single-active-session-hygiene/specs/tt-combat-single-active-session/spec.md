## ADDED Requirements

### Requirement: Exactly One Unresolved Tabletop Encounter SHALL Own Combat Input

When tabletop combat is active, the system MUST prevent a second unresolved encounter from being created or started until the current owner is cleared.

#### Scenario: Duplicate createEncounter attempt is rejected while combat is active
- **WHEN** `party_tracker.json -> worldConditions.activeCombatEncounter` already names an unresolved encounter
- **AND** tabletop action handling receives another `createEncounter` request
- **THEN** the request SHALL fail closed
- **AND** the system SHALL NOT create or start a second encounter for that live input turn
- **AND** the user SHALL receive concise `[SYSTEM]` guidance to continue the active combat instead of a second combat opening

#### Scenario: No active encounter allows normal startup
- **WHEN** no unresolved tabletop encounter owner is set
- **AND** a valid `createEncounter` request is processed
- **THEN** combat startup SHALL proceed with existing behavior
- **AND** the resulting encounter SHALL become the sole active owner

### Requirement: Runtime Combat Startup SHALL Enforce Single Session Ownership

The combat manager MUST reject concurrent or duplicate combat-loop startup inside the same process.

#### Scenario: First startup claim succeeds
- **WHEN** `run_combat_simulation(...)` starts for an encounter and no other tabletop combat loop is active
- **THEN** runtime SHALL claim single-session ownership for that encounter
- **AND** SHALL release ownership on normal completion or exceptional exit

#### Scenario: Second startup claim is rejected
- **WHEN** a second tabletop combat startup is attempted while another encounter already owns the runtime session slot
- **THEN** the second startup SHALL fail closed without consuming facilitator input
- **AND** the system SHALL emit deterministic diagnostics identifying the active and attempted encounter ids

### Requirement: Durable Owner And History Metadata SHALL Remain Coherent

Durable combat ownership and combat-history identity MUST not silently drift to different encounter ids during resume or startup.

#### Scenario: History owner matches durable owner
- **WHEN** combat history metadata and `activeCombatEncounter` refer to the same encounter
- **THEN** `/init`, `/att`, and subsequent combat commands SHALL continue against that encounter without re-entering initiative pending incorrectly

#### Scenario: History owner mismatches durable owner
- **WHEN** combat history metadata names a different encounter from `activeCombatEncounter`
- **THEN** runtime SHALL prefer the durable owner for command routing and startup decisions
- **AND** SHALL log the mismatch for operator diagnosis
- **AND** SHALL NOT create or activate a replacement encounter solely because of the mismatch

### Requirement: Existing Happy-Path Combat Behavior SHALL Remain Backward Compatible

The ownership guard MUST preserve current behavior when only one valid encounter is active.

#### Scenario: Multi-PC happy path remains unchanged
- **WHEN** a single valid tabletop encounter is active
- **THEN** `/init` SHALL lock initiative exactly once
- **AND** `/att` after successful initiative SHALL remain in the same encounter without re-triggering initiative pending

#### Scenario: Single-player behavior remains unchanged
- **WHEN** single-player combat paths execute
- **THEN** tabletop single-session ownership guards SHALL NOT change single-player combat behavior
