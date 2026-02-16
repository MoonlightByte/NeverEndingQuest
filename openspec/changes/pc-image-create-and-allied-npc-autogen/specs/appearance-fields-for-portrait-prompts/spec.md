## ADDED Requirements

### Requirement: Character schema SHALL support optional appearance metadata fields

Character schema SHALL support optional appearance fields used by portrait prompt generation.

Fields:
- `age`
- `height`
- `weight`
- `eyes`
- `skin`
- `hair`

#### Scenario: Existing character files
- **WHEN** pre-existing character files that do not contain appearance fields are loaded
- **THEN** schema validation and runtime behavior remain backward compatible

### Requirement: Creation paths SHALL accept and persist appearance fields

Manual/quick-create paths SHALL accept appearance fields and persist them when provided.

#### Scenario: Manual create with appearance values
- **WHEN** a user submits manual character creation form with appearance fields
- **THEN** saved character data includes provided appearance values

### Requirement: Portrait prompt composition SHALL include appearance metadata when available

Portrait generation prompt path SHALL include appearance fields when present and use safe defaults when absent.

#### Scenario: Partial appearance metadata
- **WHEN** only some appearance fields are available
- **THEN** prompt composition uses available fields and does not fail on missing optional values
