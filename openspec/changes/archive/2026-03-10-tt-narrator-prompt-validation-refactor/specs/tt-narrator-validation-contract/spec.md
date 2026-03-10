# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

# Spec: tt-narrator-validation-contract
# Capability: Narrator Validation Contract

## ADDED Requirements

### Requirement: Deterministic Validator Authority

The deterministic validator SHALL be the sole source of truth for off-location NPC arrival state sync hard checks.

#### Scenario: Off-location mention without action fails
**Given** a narrator output mentioning an off-location NPC (e.g., Maelo in a location where he is not present)
**And** no corresponding state action (moveBackgroundNPC, updatePartyNPCs add, etc.) in the same response
**When** the deterministic validator processes the output
**Then** it SHALL return a failure with explicit required action

#### Scenario: Present NPC mention passes
**Given** a narrator output mentioning an NPC who is already present in the current location
**When** the deterministic validator processes the output
**Then** it SHALL return a pass without requiring additional action

### Requirement: LLM Validator Non-Interference

The LLM validator SHALL NOT re-litigate deterministic pass/fail outcomes for arrival sync checks.

#### Scenario: Deterministic pass respected
**Given** a narrator output that passed deterministic validation
**And** the LLM validator receives the output with `deterministic_passed: true` in context
**When** the LLM validator processes the output
**Then** it SHALL NOT evaluate or flag arrival-sync rules
**And** it SHALL respect the deterministic pass

#### Scenario: Deterministic failure not overridden
**Given** a narrator output that failed deterministic validation
**And** the LLM validator receives the output with `deterministic_passed: false` in context
**When** the LLM validator processes the output
**Then** it MAY provide additional context
**But** it SHALL NOT change the failure classification to pass

### Requirement: No Contradictory Rule Blocks

Validation payload SHALL NOT contain simultaneously contradictory guidance blocks.

#### Scenario: Contradiction detection
**Given** a validation payload being assembled
**When** both "arrival sync required" and "do not flag missing physical presence" guidance blocks would be included
**Then** the payload assembly SHALL exclude the contradictory block
**And** deterministic validator authority SHALL take precedence

## UNCHANGED Requirements

### Requirement: Party-Member Exemption Preservation

Existing party-member exemptions from arrival-sync validation SHALL remain intact.

#### Scenario: Party member short name mention
**Given** a party member named "Scout Kira"
**And** a narrator output containing the short mention "Kira"
**When** the deterministic validator processes the output
**Then** it SHALL return pass (exempt from arrival-sync check)

### Requirement: Fail-Open Ambiguity Policy

Ambiguous NPC name mentions (matching multiple candidates) SHALL continue to fail-open.

#### Scenario: Ambiguous mention
**Given** a narrator output mentioning "the guard" which matches multiple NPCs
**When** the deterministic validator processes the output
**Then** it SHALL return pass without requiring action

## MODIFIED Requirements

### Requirement: Consistent Failure Taxonomy

Deterministic validator SHALL use consistent failure reason taxonomy for debugging.

#### Scenario: Failure classification
**Given** various arrival-sync failures
**When** the deterministic validator returns failure
**Then** reasons SHALL be one of:
  - `off_location_arrival_missing_action`
  - `ambiguous_mention`
  - `validation_error`

#### Scenario: Structured result export
**Given** a deterministic validation result
**When** exported for LLM validator consumption
**Then** format SHALL be: `{"passed": bool, "reason": str|null, "required_action": str|null}`
