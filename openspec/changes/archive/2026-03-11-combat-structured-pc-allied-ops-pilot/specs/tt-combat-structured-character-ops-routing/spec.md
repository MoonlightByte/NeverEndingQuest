## ADDED Requirements

### Requirement: Combat prompt and validator SHALL prefer additive structured PC/allied character ops
The combat prompt and combat validator contract SHALL prefer mixed `updateCharacterInfo` payloads that include both `changes` and supported `ops` for PC and allied NPC mutations.

#### Scenario: Mixed combat payload is preferred for damaged PC
- **WHEN** a combat response damages or heals a PC and emits `updateCharacterInfo`
- **THEN** the combat contract SHALL allow `characterName`, `changes`, and supported `ops` together
- **AND** the structured `ops` payload SHALL be treated as the authoritative mechanics payload when present

#### Scenario: Mixed combat payload is preferred for allied NPC ammo spend
- **WHEN** an allied NPC fires a ranged weapon in combat
- **THEN** the combat contract SHALL allow `updateCharacterInfo` to include a prose mirror in `changes`
- **AND** it SHALL prefer a supported inventory-removal op for the ammunition spend

### Requirement: Enemy-side combat mutations SHALL remain on `updateEncounter` in this slice
This change SHALL NOT widen enemy-side combat mutation routing to `updateEncounter.ops` or enemy-targeted `updateCharacterInfo`.

#### Scenario: Mixed player-and-enemy combat turn keeps enemy contract unchanged
- **WHEN** a combat response mutates both an enemy and a PC/allied NPC in the same turn
- **THEN** enemy-side state SHALL remain on `updateEncounter`
- **AND** PC/allied mutations SHALL remain on `updateCharacterInfo`

### Requirement: Combat SHALL preserve prose compatibility during structured-ops migration
Combat contract updates SHALL preserve prose-only `changes` compatibility while the mixed-payload preference rolls out.

#### Scenario: Prose-only combat payload remains valid during migration
- **WHEN** a combat response emits `updateCharacterInfo` with `characterName` and `changes` only
- **THEN** that payload SHALL remain compatibility-valid in this change
- **AND** builders SHALL NOT treat prose-only support as removed
