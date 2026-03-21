## MODIFIED Requirements

### Requirement: Phase and Prompt Contracts SHALL Remain Coherent
The combat phase value, selected active player character, turn queue ownership, and required-response instructions MUST not contradict each other within the same turn.

#### Scenario: Enemy phase contract is active
- **WHEN** current phase is `ENEMY_PHASE`
- **THEN** required-response instructions SHALL forbid player characters as acting entities
- **AND** the response SHALL process only allowed enemy or NPC actors for that batch and then stop

#### Scenario: Player phase contract is active
- **WHEN** current phase is `PC_PHASE`
- **THEN** required-response instructions SHALL allow only the selected active player-controlled turn resolution path
- **AND** enemy actions SHALL NOT be generated unless an explicit enemy-phase trigger is present (`/end` or deterministic opening-batch trigger)

#### Scenario: Manual active-PC switch occurs before command resolution
- **WHEN** tabletop runtime force-switches the active PC from tagged input or UI selection during `PC_PHASE`
- **THEN** the selected active PC, prompt actor, and current player-facing turn contract SHALL synchronize to the same canonical PC identity before the next combat prompt is assembled
- **AND** the system SHALL NOT emit a required-response block for a different stale actor from the turn queue

### Requirement: Active Encounter Ownership Remains Stable After Initiative Lock
When a tabletop encounter has accepted initiative and remains the owned active encounter, subsequent player combat commands MUST continue to resolve against that encounter and its coherent turn owner.

#### Scenario: Player combat commands continue after initiative lock
- **WHEN** a tabletop encounter has already accepted a valid `/init` and locked `initiativeWinner`
- **AND** subsequent player combat commands such as `/att` are processed
- **THEN** the runtime SHALL continue routing those commands to the same active encounter owner
- **AND** the system SHALL NOT regress to `Initiative pending` for a different duplicate encounter unless the owned encounter itself still requires `/init`

#### Scenario: Prompt actor differs from selected active PC before resolution
- **WHEN** prompt assembly detects a stale player actor different from the selected active PC during an owned active encounter
- **THEN** runtime SHALL reconcile prompt ownership to the selected active PC before issuing required-response instructions
- **AND** the resulting prompt SHALL not instruct the model to resolve another PC's action in that turn
