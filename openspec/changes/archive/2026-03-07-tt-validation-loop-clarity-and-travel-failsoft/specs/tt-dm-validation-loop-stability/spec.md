## ADDED Requirements

### Requirement: Multi-PC Turn Instructions MUST Be Non-Duplicative

The multi-PC turn assembly path MUST avoid duplicate policy injection that overloads generation.

#### Scenario: Multi-PC turn prompt assembly
- **WHEN** a multi-PC turn DM note is assembled
- **THEN** legacy common instruction tail is not appended on top of structured multi-PC note
- **AND** structured mechanical truth + action contract sections remain present

### Requirement: Transition Validator MUST Receive Raw Player Intent

Transition pre-validation MUST operate on player intent text, not on DM note payload.

#### Scenario: Travel pre-validation request payload
- **WHEN** `pre_validate_transition(...)` calls transition validation
- **THEN** `player_request` contains raw user utterance only
- **AND** path/atlas/plot context remains available to validator

### Requirement: NPC Arrival Sync MUST Stay Strict for Explicit Arrival Claims

Off-location arrival claims MUST keep fail-closed state sync behavior.

#### Scenario: Explicit off-location arrival in narration
- **WHEN** narration explicitly states an off-location NPC arrives/joins/enters/appears
- **AND** no matching `moveBackgroundNPC` or `updatePartyNPCs add` exists
- **THEN** validation fails with required-action reason

### Requirement: Travel Turns MUST Fail-Soft for Non-Arrival NPC Mentions

Travel-intent turns MUST not hard-fail on non-arrival NPC mentions that do not claim state movement.

#### Scenario: Travel turn with non-arrival mention
- **WHEN** player intent is travel
- **AND** narration includes NPC reference without explicit arrival semantics
- **THEN** NPC arrival sync does not fail this turn
- **AND** no off-location state mutation is inferred from mention alone

### Requirement: Deterministic Validation Retries MUST Avoid Self-Priming Loops

Retry logic MUST reduce repetition pressure for deterministic guard failures.

#### Scenario: Deterministic guard failure retry
- **WHEN** a deterministic validation fails (e.g., NPC arrival sync)
- **THEN** failed assistant response is not appended back into history for retry priming
- **AND** a concise normalized correction note is appended instead

#### Scenario: Repeated deterministic failure in same turn
- **WHEN** same deterministic reason repeats twice
- **THEN** retry loop short-circuits early with concise system guidance
