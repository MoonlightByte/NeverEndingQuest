# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-npc-move-hint-fallback
# Capability: NPC Movement Hint Fallback

## ADDED Requirements

### Requirement: Strict Hint First Strategy

`moveBackgroundNPC` SHALL attempt strict `currentLocation` hint match before any fallback.

#### Scenario: Correct hint success
**Given** a `moveBackgroundNPC` action with `currentLocation: RO03`
**And** an NPC "Bex" who is actually in RO03
**When** the strict hint match is attempted
**Then** it SHALL return Bex successfully
**And** fallback lookup SHALL NOT be invoked

#### Scenario: Strict hint filter applied
**Given** a `moveBackgroundNPC` action with a location hint
**When** searching for the NPC
**Then** candidates SHALL be filtered by `currentLocation == hint` first
**And** only if no match found, fallback SHALL be considered

### Requirement: Canonical Identity Fallback

If strict hint fails, the system SHALL attempt canonical identity fallback when match is unambiguous.

#### Scenario: Stale hint fallback success
**Given** a `moveBackgroundNPC` action with `currentLocation: TW03` (stale hint)
**And** an NPC "Bex" who is actually in RO03
**When** strict hint fails (no Bex in TW03)
**And** fallback search finds exactly one "Bex" in RO03
**Then** it SHALL return Bex successfully
**And** it SHALL log the fallback usage

#### Scenario: Fallback requires unambiguous match
**Given** a `moveBackgroundNPC` action with stale hint
**When** fallback search would match multiple NPCs
**Then** fallback SHALL NOT be applied
**And** it SHALL return an error

### Requirement: Fail-Closed on Ambiguity

Fallback SHALL fail-closed when NPC match is ambiguous.

#### Scenario: Ambiguous match failure
**Given** a `moveBackgroundNPC` action for "caravan guard" with stale hint
**When** fallback search finds 3 "caravan guard" NPCs in different locations
**Then** it SHALL return error "Ambiguous NPC match for caravan guard: 3 candidates found"
**And** no NPC SHALL be moved

#### Scenario: No match failure
**Given** a `moveBackgroundNPC` action for non-existent NPC
**When** strict hint fails
**And** fallback finds zero matches
**Then** it SHALL return error "NPC not found"

## UNCHANGED Requirements

### Requirement: Function Signature Compatibility

Existing `moveBackgroundNPC` function signature SHALL remain unchanged.

#### Scenario: API compatibility
**Given** existing callers of `moveBackgroundNPC`
**When** they invoke the function
**Then** parameters SHALL remain unchanged
**And** return format SHALL remain unchanged

### Requirement: Fail-Closed Behavior Preservation

Existing fail-closed behavior for unmatched NPCs SHALL be preserved.

#### Scenario: Unmatched NPC
**Given** a `moveBackgroundNPC` action for an NPC that cannot be found
**When** processing the action
**Then** it SHALL return an error
**And** no NPC SHALL be moved
**And** error format SHALL match existing conventions

## MODIFIED Requirements

### Requirement: Fallback Usage Logging

Fallback usage SHALL be logged for monitoring and data quality improvement.

#### Scenario: Fallback log entry
**Given** a successful fallback resolution
**When** the fallback is applied
**Then** it SHALL log: `NPC_MOVE_FALLBACK: name={name} stale_hint={hint} resolved_location={location} timestamp={ts}`

#### Scenario: Stale hint identification
**Given** fallback logs over time
**When** analyzing the logs
**Then** frequently stale hints SHALL be identifiable
**And** data quality improvements can be prioritized
