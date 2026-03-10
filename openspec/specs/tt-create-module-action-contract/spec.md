# tt-create-module-action-contract Specification

## Purpose
TBD - created by archiving change prompt-validator-save-module-contract-alignment. Update Purpose after archive.
## Requirements
### Requirement: `createNewModule` SHALL use a narrative-driven validator contract
`createNewModule` SHALL be documented and validated as a narrative-driven handoff action that matches current runtime behavior.

#### Scenario: Canonical minimum payload
- **WHEN** the narrator emits `createNewModule`
- **THEN** the canonical minimum payload SHALL include `{"narrative": str}`
- **AND** validator guidance SHALL accept that payload shape as sufficient for the narrator layer

#### Scenario: Optional overrides remain additive
- **WHEN** runtime supports optional override fields alongside `narrative`
- **THEN** validator guidance MAY allow those fields
- **AND** it SHALL NOT require them unless runtime requires them

### Requirement: Validator SHALL reject rigid stale module-creation schema assumptions
Validator guidance SHALL not require a stale fixed two-field shape that does not match runtime.

#### Scenario: Rigid `moduleName` plus `startingLocation` requirement removed
- **WHEN** validator guidance describes `createNewModule`
- **THEN** it SHALL NOT require `moduleName` and `startingLocation` as the only valid parameter shape
- **AND** it SHALL align with the narrative-driven runtime handoff

### Requirement: Existing user-commitment gate SHALL remain intact
Prompt and validator alignment SHALL preserve the existing requirement that `createNewModule` only follows clear player commitment to an adventure hook.

#### Scenario: Vague prompt still invalid
- **WHEN** the player only asks a vague question such as `What next?`
- **THEN** validation SHALL continue to reject `createNewModule`
- **AND** prompt alignment SHALL not weaken that gate

### Requirement: Create-module prompt parity SHALL cover both prompt variants
Compressed and uncompressed system/validation prompt files SHALL mirror the same `createNewModule` contract for this slice.

#### Scenario: Prompt variant parity regression
- **WHEN** either prompt variant drifts from the narrative-driven `createNewModule` contract
- **THEN** the parity regression suite SHALL fail

