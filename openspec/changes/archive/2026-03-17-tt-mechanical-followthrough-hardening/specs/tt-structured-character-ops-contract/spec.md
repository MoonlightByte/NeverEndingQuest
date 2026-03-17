## MODIFIED Requirements

### Requirement: `updateCharacterInfo` SHALL support additive structured ops

`updateCharacterInfo.parameters` SHALL support an additive `ops` field without breaking legacy `changes` support.

#### Scenario: Legacy prose payload remains valid
- **WHEN** the narrator emits `updateCharacterInfo` with only `characterName` and `changes`
- **THEN** the payload SHALL remain valid

#### Scenario: Mixed payload remains valid
- **WHEN** the narrator emits `updateCharacterInfo` with `characterName`, `changes`, and `ops`
- **THEN** the payload SHALL remain valid
- **AND** the structured `ops` contract SHALL be recognized

### Requirement: Structured ops SHALL use a canonical flat record shape

Structured ops SHALL use canonical flat records with an explicit `op` field at runtime.

#### Scenario: Canonical flat op shape recognized
- **WHEN** the narrator emits an op such as `{"op":"inventory_remove","item":"Healing Potion","quantity":1}`
- **THEN** runtime SHALL recognize and classify that op deterministically

### Requirement: Runtime SHALL normalize unambiguous legacy nested op wrappers

Runtime SHALL normalize legacy single-key nested wrappers into canonical flat ops when the intended op type is unambiguous.

#### Scenario: Nested inventory remove wrapper normalized
- **WHEN** the narrator emits an op shaped like `{"inventory_remove":{"item":"Healing Potion","quantity":1}}`
- **THEN** runtime SHALL normalize it to the canonical flat `inventory_remove` op before deterministic application
- **AND** SHALL preserve fail-safe behavior for malformed wrappers that are not safely normalizable

### Requirement: Supported ops set SHALL include deterministic class-feature usage updates

The documented and runtime-supported structured ops set SHALL include deterministic class-feature usage updates.

#### Scenario: Supported ops set documented
- **WHEN** the contract is reviewed
- **THEN** it SHALL explicitly include `set_hp`, `hp_delta`, `spell_slot_delta`, `inventory_add`, `inventory_remove`, `currency_delta`, `condition_add`, `condition_remove`, `feature_usage_delta`, and `feature_usage_set`
