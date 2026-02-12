## ADDED Requirements

### Requirement: Saving throw proficiency matching SHALL be case-insensitive and canonical
The system SHALL normalize saving throw proficiency values into canonical ability keys and treat equivalent forms as identical (for example `Intelligence`, `intelligence`, `INT`).

#### Scenario: Mixed-case proficiency values
- **WHEN** character data contains `savingThrows` values in mixed casing or abbreviations
- **THEN** proficiency checks in GUI and PDF use canonical normalized values

#### Scenario: Unknown proficiency token
- **WHEN** `savingThrows` includes unknown values
- **THEN** unknown tokens are ignored safely without breaking rendering/export

### Requirement: GUI character sheet SHALL always render six saving throws
The web character sheet SHALL always display the Saving Throws panel with six abilities regardless of whether `savingThrows` is empty.

#### Scenario: Empty savingThrows array
- **WHEN** `savingThrows` is empty for a character
- **THEN** sheet still renders all six saves with computed bonuses and proficiency indicators based on fallback rules

#### Scenario: Existing non-empty savingThrows array
- **WHEN** `savingThrows` is present and valid
- **THEN** sheet renders all six saves with proficiency indicators matching normalized proficiency values

### Requirement: Class-based fallback proficiencies SHALL be applied when savingThrows is empty
When no explicit `savingThrows` are present, the system SHALL derive proficiency defaults from class identity (including known aliases).

#### Scenario: Thief alias fallback
- **WHEN** class is `Thief` and `savingThrows` is empty
- **THEN** fallback proficiencies are applied using Rogue defaults

#### Scenario: Unknown class fallback
- **WHEN** class is unknown and `savingThrows` is empty
- **THEN** system applies no proficiency fallback and still renders all six saves

### Requirement: PDF export SHALL match GUI saving throw proficiency behavior
PDF saving throw modifiers and proficiency checkboxes SHALL use the same normalized/fallback proficiency source as GUI.

#### Scenario: Legacy title-case savingThrows values
- **WHEN** character data uses title-case values like `Wisdom`
- **THEN** PDF checkboxes and bonuses reflect proficiency correctly

#### Scenario: Empty savingThrows with class fallback
- **WHEN** `savingThrows` is empty but class has known defaults
- **THEN** PDF saving throw values and checkboxes use fallback proficiencies

### Requirement: Backward compatibility SHALL be preserved
Changes SHALL preserve existing schema and not require character file format migration to function.

#### Scenario: Existing complete character remains stable
- **WHEN** character already has valid savingThrows values
- **THEN** rendering/export results are unchanged except for normalization-equivalent matching
