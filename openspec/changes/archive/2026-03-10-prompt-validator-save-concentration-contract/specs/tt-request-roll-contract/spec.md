## ADDED Requirements

### Requirement: Player-facing saves and checks SHALL support a lightweight `requestRoll` contract
The narrator and validator contract SHALL support a first-class `requestRoll` action for player-facing saving throws and checks without breaking prose-only compatibility during migration.

#### Scenario: Structured save request payload
- **WHEN** the narrator needs a player saving throw or check before continuing resolution
- **THEN** it MAY emit `requestRoll`
- **AND** `requestRoll.parameters` SHALL include `characterName`, `rollType`, `dc`, and `reason`
- **AND** it SHALL include `ability` for `saving_throw` and `ability_check`
- **AND** it SHALL include `skill` for `skill_check`
- **AND** it MAY include `advantage` with values `normal`, `advantage`, or `disadvantage`

#### Scenario: Pause after structured roll request
- **WHEN** a response emits `requestRoll`
- **THEN** that response SHALL stop before narrating contingent player-roll success or failure

#### Scenario: Prose-only compatibility remains valid during migration
- **WHEN** the narrator asks for a save or check in prose without `requestRoll`
- **THEN** the turn SHALL remain compatibility-valid until a later change explicitly tightens that contract

### Requirement: `requestRoll` roll types SHALL remain narrow
The initial `requestRoll` contract SHALL remain limited to `saving_throw`, `ability_check`, and `skill_check`.

#### Scenario: Initial roll type set reviewed
- **WHEN** the contract is reviewed
- **THEN** it SHALL NOT expand beyond `saving_throw`, `ability_check`, and `skill_check` in this change
