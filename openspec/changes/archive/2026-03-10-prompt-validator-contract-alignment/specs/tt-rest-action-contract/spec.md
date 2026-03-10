## ADDED Requirements

### Requirement: Rest SHALL be expressed as a dedicated narrator action
Rest handling SHALL use the dedicated `rest` action contract rather than requiring the narrator to directly encode recovery effects as `updateCharacterInfo` actions.

#### Scenario: Short rest response shape
- **WHEN** the narrator determines that the party is taking a short rest
- **THEN** the response SHALL include a `rest` action with `type="short"`
- **AND** any required time passage SHALL be represented with `updateTime` in the same response bundle

#### Scenario: Long rest response shape
- **WHEN** the narrator determines that the party is taking a long rest
- **THEN** the response SHALL include a `rest` action with `type="long"`
- **AND** any required time passage SHALL be represented with `updateTime` in the same response bundle

### Requirement: Both prompt variants SHALL describe the same rest contract
Compressed and uncompressed system/validation prompt files SHALL mirror the same dedicated `rest` action contract for the covered slice.

#### Scenario: System prompt variant parity
- **WHEN** either `prompts/system_prompt.txt` or `prompts/system_prompt_compressed.txt` is reviewed for the covered `rest` contract
- **THEN** both SHALL describe `rest` as the narrator-facing action
- **AND** neither SHALL present direct `updateCharacterInfo` recovery as the primary narrator contract for rest

#### Scenario: Validation prompt variant parity
- **WHEN** either validation prompt variant is reviewed for the covered `rest` contract
- **THEN** both SHALL accept `rest` plus `updateTime` as the canonical narrator bundle
- **AND** neither SHALL reject valid rest responses solely for omitting narrator-authored recovery deltas

### Requirement: Validator SHALL accept the dedicated rest action contract
Validation SHALL treat the dedicated `rest` action as the canonical rest contract for the narrator layer.

#### Scenario: Rest response passes without direct recovery deltas
- **WHEN** a valid rest response includes `rest` and `updateTime`
- **THEN** validation SHALL NOT reject the response solely because it omits direct `updateCharacterInfo` recovery actions for rest benefits

#### Scenario: Stale rest guidance removed
- **WHEN** validator guidance describes rest handling
- **THEN** it SHALL describe the dedicated `rest` action contract
- **AND** it SHALL NOT require narrator-authored direct recovery updates as the primary rest mechanism

### Requirement: Runtime SHALL remain authoritative for rest recovery semantics
Python runtime SHALL continue to own the mechanical effects of the `rest` action.

#### Scenario: Short rest runtime ownership
- **WHEN** runtime processes a `rest` action with `type="short"`
- **THEN** runtime SHALL apply only the short-rest benefits supported by the current system contract

#### Scenario: Long rest runtime ownership
- **WHEN** runtime processes a `rest` action with `type="long"`
- **THEN** runtime SHALL apply the long-rest benefits supported by the current system contract
- **AND** narrator validation SHALL align with that runtime-owned behavior
