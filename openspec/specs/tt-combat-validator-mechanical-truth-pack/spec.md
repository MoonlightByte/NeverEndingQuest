## Purpose

Provide compact touched-combatant mechanical truth packs during combat validation so the validator can verify PC/allied mutations against actual current state, including nested feature usage and live-schema inventory/ammo data when relevant.

## Requirements

### Requirement: Combat validator context SHALL use touched-combatant truth packs for PC/allied mutations

When a candidate combat response mutates PCs or allied NPCs through `updateCharacterInfo`, the combat validator SHALL receive compact touched-combatant mechanical truth packs for those entities.

#### Scenario: Touched combatant truth pack provided
- **WHEN** the candidate combat response contains one or more `updateCharacterInfo` actions for PCs or allied NPCs
- **THEN** combat validation context SHALL include one compact truth pack per touched combatant
- **AND** each pack SHALL include HP/max HP, conditions, spell slots, and death-save or class-feature state when present

#### Scenario: Nested combat resource usage is surfaced
- **WHEN** a touched combatant stores limited-use feature state under `classFeatures[].usage`
- **THEN** the combat truth pack SHALL surface that current/max usage state in compact form
- **AND** SHALL NOT rely only on legacy flat `uses`-style keys

#### Scenario: Inventory or ammo included from live schema when relevant
- **WHEN** the touched combatant change text is inventory-relevant or ammunition-relevant
- **THEN** the touched-combatant truth pack SHALL include compact inventory, ammo, or currency summary data built from live schema fields
- **AND** inventory-style data SHALL be omitted for clearly non-inventory combat mutations
