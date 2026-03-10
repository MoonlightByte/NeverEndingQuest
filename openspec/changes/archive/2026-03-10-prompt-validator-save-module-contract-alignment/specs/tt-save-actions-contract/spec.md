## ADDED Requirements

### Requirement: Save-management actions SHALL use the runtime parameter contract across prompt, validator, and runtime
The covered save-management actions SHALL use one consistent contract across narrator prompt text, validator prompt text, and runtime handling.

#### Scenario: Save game canonical shape
- **WHEN** the narrator emits `saveGame`
- **THEN** the canonical contract SHALL be `{"description": str_opt, "saveMode": str_opt}`
- **AND** validator guidance SHALL NOT require a `saveName` field for that action

#### Scenario: Restore game canonical shape
- **WHEN** the narrator emits `restoreGame`
- **THEN** the canonical contract SHALL be `{"saveFolder": str}`
- **AND** validator guidance SHALL NOT require `saveName` as the canonical restore identifier

#### Scenario: Delete save canonical shape
- **WHEN** the narrator emits `deleteSave`
- **THEN** the canonical contract SHALL be `{"saveFolder": str}`
- **AND** validator guidance SHALL NOT require `saveName` as the canonical delete identifier

#### Scenario: List saves canonical shape
- **WHEN** the narrator emits `listSaves`
- **THEN** the canonical contract SHALL be an empty parameter object

### Requirement: Save-management prompt parity SHALL cover both prompt variants
Compressed and uncompressed prompt/validator files SHALL mirror the same save-management contract.

#### Scenario: Prompt variant parity regression
- **WHEN** either compressed or uncompressed prompt copies drift from the covered save-management runtime contract
- **THEN** the parity regression suite SHALL fail
- **AND** the failure SHALL identify the drifted prompt variant

### Requirement: Save-management validator guidance SHALL reject stale parameter drift
Validator guidance SHALL not preserve stale save parameter rules once this change lands.

#### Scenario: Stale `saveName` guidance removed
- **WHEN** validator guidance is reviewed for `restoreGame` or `deleteSave`
- **THEN** it SHALL use `saveFolder` as the canonical runtime identifier
- **AND** it SHALL NOT present `saveName` as the required parameter for those actions
