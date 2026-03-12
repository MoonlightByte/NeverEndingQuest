# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-narrator-validation-contract
# Capability: Narrator Validation Contract

## MODIFIED Requirements

### Requirement: Deterministic validator is authoritative for arrival sync

Off-location NPC mention SHALL require a state-sync action only when narration includes explicit physical-arrival semantics.

#### Scenario: Off-location rumor mention without explicit arrival
- **GIVEN** narration references an off-location known NPC in informational/social context
- **AND** no explicit arrival verb semantics are present
- **WHEN** deterministic arrival validation runs
- **THEN** validation SHALL pass for arrival-sync dimension

#### Scenario: Explicit off-location arrival without action
- **GIVEN** narration explicitly states an off-location known NPC arrives/enters/joins/appears
- **AND** no matching `moveBackgroundNPC` or `updatePartyNPCs add` action exists
- **WHEN** deterministic arrival validation runs
- **THEN** validation SHALL fail with required-action reason

### Requirement: LLM validator SHALL NOT re-litigate deterministic arrival results

LLM validation SHALL NOT reintroduce arrival-sync failure when deterministic arrival-sync pass condition is satisfied.

#### Scenario: Deterministic pass for non-explicit mention
- **GIVEN** deterministic validator marks arrival-sync pass for a non-explicit off-location mention
- **WHEN** LLM validation executes
- **THEN** runtime SHALL keep arrival-sync as pass
- **AND** SHALL evaluate only non-arrival semantic dimensions

## UNCHANGED Requirements

### Requirement: Party-member exemptions are preserved

Party-member mentions remain exempt from NPC arrival-sync enforcement.

### Requirement: Ambiguity remains fail-open for mention classification

Ambiguous mention identity SHALL not independently trigger hard fail for arrival-sync.
