# tt-combat-request-roll-routing Specification

## Purpose
TBD - created by archiving change combat-save-concentration-contract. Update Purpose after archive.
## Requirements
### Requirement: Combat prompt and validator SHALL prefer `requestRoll` for player-facing saves and checks
The multi-PC combat prompt and combat validator SHALL prefer `requestRoll` for player-facing saving throws, ability checks, and skill checks.

#### Scenario: Combat saving throw pause uses requestRoll
- **WHEN** combat needs a player saving throw before continuing resolution
- **THEN** the combat contract SHALL allow and prefer `requestRoll`
- **AND** the same response SHALL stop after issuing the request

#### Scenario: Combat ability or skill check pause uses requestRoll
- **WHEN** combat needs a player ability check or skill check before continuing resolution
- **THEN** the combat contract SHALL allow and prefer `requestRoll`
- **AND** the same response SHALL NOT narrate contingent success or failure after issuing the request

### Requirement: Combat SHALL preserve prose-only compatibility during migration
This change SHALL preserve prose-only save/check requests as compatibility-valid during migration.

#### Scenario: Prose-only combat save request remains valid during migration
- **WHEN** a combat response asks for a save or check in prose without `requestRoll`
- **THEN** that response SHALL remain compatibility-valid in this change
- **AND** builders SHALL NOT treat prose-only support as removed

