## MODIFIED Requirements

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
