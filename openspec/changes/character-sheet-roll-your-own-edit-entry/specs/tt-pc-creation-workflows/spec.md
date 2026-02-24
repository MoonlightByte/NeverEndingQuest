## MODIFIED Requirements

### Requirement: Roll Your Own SHALL support both create and edit entry points
The Roll Your Own workflow SHALL support both create mode (existing Manage Party flow) and edit mode (new Character Sheet `Edit` entry) while preserving create semantics.

#### Scenario: Create mode remains unchanged
- **WHEN** Roll Your Own is opened from Manage Party for a new character
- **THEN** submit continues to use the create path and create-only side effects remain as currently defined

#### Scenario: Edit mode uses existing character context
- **WHEN** Roll Your Own is opened from Character Sheet `Edit`
- **THEN** form mode is edit, existing values are prefilled, and submit routes to the deterministic edit path

#### Scenario: Name safety in MVP edit mode
- **WHEN** Roll Your Own is opened in edit mode
- **THEN** character name is treated as fixed identity input (read-only or equivalent guarded behavior)
