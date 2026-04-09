# tt-combat-structured-encounter-ops-routing Specification

## Purpose
TBD - created by archiving change combat-encounter-ops-second-wave. Update Purpose after archive.
## Requirements
### Requirement: Combat prompt and validator SHALL prefer additive structured enemy encounter ops
The combat prompt and combat validator contract SHALL prefer mixed `updateEncounter` payloads that include both `changes` and supported `ops` for enemy-side combat mutations.

#### Scenario: Mixed combat payload is preferred for damaged enemy
- **WHEN** a combat response damages or heals an enemy and emits `updateEncounter`
- **THEN** the combat contract SHALL allow `encounterId`, `changes`, and supported `ops` together
- **AND** the structured `ops` payload SHALL be treated as the authoritative mechanics payload when present

#### Scenario: Mixed combat payload is preferred for enemy condition change
- **WHEN** a combat response applies or removes a condition on an enemy and emits `updateEncounter`
- **THEN** the combat contract SHALL allow a prose mirror in `changes`
- **AND** it SHALL prefer a supported condition op in `ops`

### Requirement: Combat SHALL preserve routing separation between enemy encounter ops and PC/allied character ops
This change SHALL NOT widen enemy-side combat mutations onto `updateCharacterInfo`, and it SHALL NOT collapse PC/allied mutations into `updateEncounter`. Enemy encounter payloads MUST remain enemy-only in both prose mirrors and supported ops.

#### Scenario: Mixed player-and-enemy combat turn keeps routing boundary intact
- **WHEN** a combat response mutates both an enemy and a PC or allied NPC in the same turn
- **THEN** enemy-side state SHALL remain on `updateEncounter`
- **AND** PC/allied state SHALL remain on `updateCharacterInfo`

#### Scenario: Player target in updateEncounter ops is rejected
- **WHEN** a combat response includes `updateEncounter.parameters.ops`
- **AND** any supported op references a player character or allied NPC target
- **THEN** combat validation SHALL reject the response before probabilistic validation

#### Scenario: Player or allied state mutation in updateEncounter prose mirror is rejected
- **WHEN** a combat response includes `updateEncounter.parameters.changes`
- **AND** that prose mirror explicitly applies HP, status, condition, or ammo/inventory mutation to a player character or allied NPC
- **THEN** combat validation SHALL reject the response before probabilistic validation

### Requirement: Combat SHALL preserve compatibility fallback during enemy encounter-ops migration
Combat contract updates SHALL preserve prose-only `changes` compatibility and fail-open fallback for unsupported or ambiguous enemy ops payloads during migration.

#### Scenario: Prose-only enemy payload remains valid during migration
- **WHEN** a combat response emits `updateEncounter` with `encounterId` and `changes` only
- **THEN** that payload SHALL remain compatibility-valid in this change
- **AND** builders SHALL NOT treat prose-only enemy support as removed

#### Scenario: Unsupported enemy ops do not remove safe fallback behavior
- **WHEN** a combat response emits partial, unsupported, or ambiguous enemy `ops`
- **THEN** the combat contract SHALL preserve safe fallback behavior instead of requiring broad new runtime handling

