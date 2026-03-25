## Purpose

Define deterministic opening-phase and ongoing phase-contract synchronization for multi-PC combat turns.

## Requirements

### Requirement: DM-Group Opening Batch SHALL Transition Back to PC Phase
When `initiativeWinner` is `dmGroup` at combat start, the system MUST process exactly one opening enemy batch and then transition to `PC_PHASE` for player control unless combat has already ended.

#### Scenario: Enemy-first opening batch completes
- **WHEN** combat starts with `initiativeWinner=dmGroup` and at least one enemy action is resolved
- **THEN** the system SHALL clear the opening-batch pending state and set phase state to `PC_PHASE` for subsequent player turns
- **AND** subsequent prompts SHALL stop treating player characters as forbidden actors until the next explicit enemy-phase trigger

#### Scenario: Opening batch has no executable enemy turns
- **WHEN** combat starts with `initiativeWinner=dmGroup` but no living enemy/NPC actor is available for the opening batch
- **THEN** the system SHALL clear the opening-batch pending state without entering a repeated enemy-phase loop
- **AND** control SHALL proceed to normal phase evaluation (player phase or combat end)

### Requirement: Phase and Prompt Contracts SHALL Remain Coherent
The combat phase value, selected active player character, turn queue ownership, and required-response instructions MUST not contradict each other within the same turn.

#### Scenario: Enemy phase contract is active
- **WHEN** current phase is `ENEMY_PHASE`
- **THEN** required-response instructions SHALL forbid player characters as acting entities
- **AND** the response SHALL process only allowed enemy/NPC actors for that batch and then stop

#### Scenario: Player phase contract is active
- **WHEN** current phase is `PC_PHASE`
- **THEN** required-response instructions SHALL allow only the selected active player-controlled turn resolution path
- **AND** enemy actions SHALL NOT be generated unless an explicit enemy-phase trigger is present (`/end` or deterministic opening-batch trigger)

#### Scenario: Manual active-PC switch occurs before command resolution
- **WHEN** tabletop runtime force-switches the active PC from tagged input or UI selection during `PC_PHASE`
- **THEN** the selected active PC, prompt actor, and current player-facing turn contract SHALL synchronize to the same canonical PC identity before the next combat prompt is assembled
- **AND** the system SHALL NOT emit a required-response block for a different stale actor from the turn queue

#### Scenario: Active encounter ownership remains stable after initiative lock
- **WHEN** a tabletop encounter has already accepted a valid `/init` and locked `initiativeWinner`
- **AND** subsequent player combat commands such as `/att` are processed
- **THEN** the runtime SHALL continue routing those commands to the same active encounter owner
- **AND** the system SHALL NOT regress to `Initiative pending` for a different duplicate encounter unless the owned encounter itself still requires `/init`

#### Scenario: Prompt actor differs from selected active PC before resolution
- **WHEN** prompt assembly detects a stale player actor different from the selected active PC during an owned active encounter
- **THEN** runtime SHALL reconcile prompt ownership to the selected active PC before issuing required-response instructions
- **AND** the resulting prompt SHALL not instruct the model to resolve another PC's action in that turn

### Requirement: Existing Initiative Start Modes SHALL Remain Backward Compatible
The phase sync fix MUST preserve behavior for `pcGroup` starts and existing non-phase1 encounters.

#### Scenario: PC-group start remains unchanged
- **WHEN** initiative starts with `initiativeWinner=pcGroup`
- **THEN** combat SHALL begin in `PC_PHASE` without opening enemy batch injection
- **AND** turn progression SHALL match prior behavior for player-driven action flow

#### Scenario: Legacy encounter without new marker
- **WHEN** an existing encounter file lacks new additive opening-phase metadata
- **THEN** the system SHALL fail open to current logic without crashing
- **AND** SHALL emit diagnostic logging sufficient to identify phase-state source
