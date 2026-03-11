# tt-combat-validator-mechanical-truth-pack Specification

## Purpose
TBD - created by archiving change combat-runtime-authority-and-efficiency. Update Purpose after archive.
## Requirements
### Requirement: Combat validator context SHALL use touched-combatant truth packs for PC/allied mutations
When a candidate combat response mutates PCs or allied NPCs through `updateCharacterInfo`, the combat validator SHALL receive compact touched-combatant mechanical truth packs for those entities.

#### Scenario: Touched combatant truth pack provided
- **WHEN** the candidate combat response contains one or more `updateCharacterInfo` actions for PCs or allied NPCs
- **THEN** combat validation context SHALL include one compact truth pack per touched combatant
- **AND** each pack SHALL include HP/max HP, conditions, spell slots, and death-save or class-feature state when present

#### Scenario: Inventory or ammo included only when relevant
- **WHEN** the touched combatant change text is inventory-relevant or ammunition-relevant
- **THEN** the touched-combatant truth pack SHALL include compact inventory or ammo summary data
- **AND** inventory-style data SHALL be omitted for clearly non-inventory combat mutations

