# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-npc-arrival-name-resolution
# Capability: NPC Arrival Name Resolution

## MODIFIED Requirements

### Requirement: Canonical identity checks SHALL be action-type invariant

Canonical name resolution SHALL be scoped by action type to avoid impossible validation loops.

#### Scenario: updatePartyNPCs add uses party-tracker canonical identity
- **GIVEN** an `updatePartyNPCs` action payload
- **WHEN** canonical name preprocessing runs
- **THEN** name resolution SHALL use party tracker canonical identities

#### Scenario: moveBackgroundNPC uses module-known canonical identity
- **GIVEN** a `moveBackgroundNPC` action payload
- **WHEN** canonical name preprocessing runs
- **THEN** name resolution SHALL use module-known NPC canonical identities
- **AND** SHALL NOT be rejected solely for absence from party tracker

### Requirement: Action-name alias handling SHALL match mention alias handling

State mutation actions with ambiguous canonical identity SHALL fail closed.

#### Scenario: moveBackgroundNPC ambiguous candidate set
- **GIVEN** `moveBackgroundNPC` npcName resolves to multiple module NPC candidates
- **WHEN** preprocessing runs
- **THEN** validation SHALL fail with explicit ambiguity reason
- **AND** no mutation action SHALL execute

## UNCHANGED Requirements

### Requirement: Unambiguous short/full aliases resolve consistently

Unambiguous short and full name variants SHALL continue to resolve to same canonical identity.
