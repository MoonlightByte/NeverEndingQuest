## Purpose

Define additive appearance/profile metadata requirements and portrait prompt composition contracts for robust, context-aware portrait generation.

## Requirements

### Requirement: Character schema SHALL support optional appearance metadata fields

Character schema SHALL support optional appearance fields used by portrait prompt generation.

#### Scenario: Existing character files
- **WHEN** pre-existing character files that do not contain appearance fields are loaded
- **THEN** schema validation and runtime behavior remain backward compatible

### Requirement: Creation paths SHALL accept and persist appearance fields

Manual and quick-create paths SHALL accept appearance fields and persist them when provided.

#### Scenario: Manual create with appearance values
- **WHEN** a user submits manual character creation form with appearance fields
- **THEN** saved character data includes provided appearance values

### Requirement: Portrait prompt composition SHALL include appearance metadata when available

Portrait generation prompt path SHALL include appearance fields when present and use safe defaults when absent.

#### Scenario: Partial appearance metadata
- **WHEN** only some appearance fields are available
- **THEN** prompt composition uses available fields and does not fail on missing optional values

### Requirement: Portrait prompt composition SHALL include personality and background context when available

Portrait generation prompt path SHALL include personality and background context fields when present.

#### Scenario: Personality/background context present
- **WHEN** character data includes personality/background fields
- **THEN** prompt composition includes those fields in a safe portrait-context section

### Requirement: Portrait prompt free-text context SHALL be sanitized and bounded

Portrait prompt composition SHALL sanitize and length-bound free-text profile inputs to prevent malformed or unbounded prompt payloads.

#### Scenario: Very long personality text
- **WHEN** a character has long free-text values in personality/background fields
- **THEN** prompt composition trims and bounds those values without failing generation

### Requirement: NPC to PC promotion flows SHALL expose profile-readiness warnings for optional appearance fields

Promotion workflows SHALL surface missing optional appearance/profile fields as readiness warnings while preserving promotion viability.

#### Scenario: Promote NPC with missing appearance metadata
- **WHEN** an NPC companion is promoted and appearance fields are absent
- **THEN** API responses include deterministic readiness warnings for missing profile fields
- **AND** promotion does not fail solely due to missing optional appearance metadata
