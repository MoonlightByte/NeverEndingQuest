## Purpose

Define a deterministic structured operations contract for `updateCharacterInfo` that supports canonical flat op records, normalizes legacy nested wrappers for backward compatibility, and includes class-feature usage updates—all while preserving prose fallback behavior.
## Requirements
### Requirement: `updateCharacterInfo` SHALL support additive structured ops
`updateCharacterInfo.parameters` SHALL support an additive `ops` field without breaking legacy `changes` support. Mixed payloads with both `changes` and `ops` SHALL remain valid even when deterministic apply later needs recoverable fallback.

#### Scenario: Legacy prose payload remains valid
- **WHEN** the narrator emits `updateCharacterInfo` with only `characterName` and `changes`
- **THEN** the payload SHALL remain valid

#### Scenario: Mixed payload remains valid
- **WHEN** the narrator emits `updateCharacterInfo` with `characterName`, `changes`, and `ops`
- **THEN** the payload SHALL remain valid
- **AND** the structured `ops` contract SHALL be recognized

#### Scenario: Mixed payload preserves recoverable fallback eligibility
- **WHEN** a mixed payload includes deterministic `ops` and prose `changes`
- **THEN** runtime SHALL preserve the prose path as a recoverable fallback option
- **AND** SHALL NOT treat the mere presence of syntactically valid `ops` as a guarantee that the turn must hard-fail

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

### Requirement: Runtime SHALL canonicalize deterministic character ops targets before apply-time rejection
Runtime SHALL canonicalize supported deterministic target labels before rejecting a character op for unknown target mismatch.

#### Scenario: Compact class feature alias resolves to persisted feature name
- **WHEN** a supported character op targets a class feature using a compact or punctuation-stripped alias such as `DivineSense`
- **THEN** runtime SHALL canonicalize that label against persisted `classFeatures[].name`
- **AND** it SHALL match the corresponding persisted feature `Divine Sense` when the identity is unambiguous

#### Scenario: Ambiguous canonical target remains blocked
- **WHEN** canonical target matching yields multiple plausible targets or no unambiguous target
- **THEN** runtime SHALL NOT guess which target to mutate
- **AND** it SHALL preserve fail-closed behavior for that target resolution attempt

### Requirement: Legacy and compact target forms SHALL remain backward compatible across supported ops
Canonical target normalization SHALL preserve backward compatibility for supported deterministic ops that reference feature, item, ammunition, or other runtime-owned targets through alternate but semantically equivalent labels.

#### Scenario: Item target with formatting drift still resolves
- **WHEN** a supported inventory or ammunition op references an existing target using an alternate spacing, punctuation, or compacted form
- **THEN** runtime SHALL resolve that target if the identity is unambiguous
- **AND** deterministic application SHALL proceed without requiring a one-off alias patch for that specific label

