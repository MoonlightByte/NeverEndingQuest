## Purpose
Define combat request-roll routing rules for player-facing checks, saves, and death-save pauses in multi-PC combat.

## Requirements
### Requirement: Combat prompt and validator SHALL prefer `requestRoll` for player-facing saves and checks
The multi-PC combat prompt and combat validator SHALL prefer `requestRoll` for player-facing saving throws, ability checks, skill checks, and start-of-turn death saving throws.

#### Scenario: Combat saving throw pause uses requestRoll
- **WHEN** combat needs a player saving throw before continuing resolution
- **THEN** the combat contract SHALL allow and prefer `requestRoll`
- **AND** the same response SHALL stop after issuing the request

#### Scenario: Combat ability or skill check pause uses requestRoll
- **WHEN** combat needs a player ability check or skill check before continuing resolution
- **THEN** the combat contract SHALL allow and prefer `requestRoll`
- **AND** the same response SHALL NOT narrate contingent success or failure after issuing the request

#### Scenario: Unconscious active PC requires death save
- **WHEN** the active PC starts their combat turn at 0 HP and unconscious
- **THEN** the combat contract SHALL issue a `requestRoll` for that PC's death saving throw before any ordinary action flow
- **AND** the response SHALL stop without narrating a normal attack, spell, or enemy turn on behalf of that PC
