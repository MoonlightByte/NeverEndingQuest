## ADDED Requirements

### Requirement: Enemy Defeat State SHALL Converge Before Encounter Persistence
When combat runtime applies enemy-state mutations, Python SHALL persist a single authoritative defeated-enemy result before the encounter state is reused by targeting, queue sync, or initiative UI consumers.

#### Scenario: Enemy HP is reduced below zero by deterministic update
- **WHEN** an enemy `currentHitPoints` is reduced to `0` or below by fast-lane `/dmg`, supported encounter ops, or equivalent Python-side combat mutation
- **THEN** runtime SHALL clamp the persisted enemy HP to `0`
- **AND** runtime SHALL assign a schema-legal non-living status before the encounter file is reused

#### Scenario: Legacy or fallback encounter update leaves alive status with zero-or-negative HP
- **WHEN** encounter update processing would otherwise persist an enemy with `currentHitPoints <= 0` and `status = alive`
- **THEN** runtime SHALL normalize that enemy to a defeated mechanical state before persistence completes
- **AND** subsequent readers SHALL not receive the contradictory alive-state payload

### Requirement: Defeated Enemies SHALL Not Remain Advertised As Living Combatants
Turn-queue state, local target resolution, and initiative UI visibility SHALL converge on the same non-living rule for defeated non-player combatants.

#### Scenario: Defeated enemy remains in in-memory queue after encounter update
- **WHEN** immediate combat processing updates enemy HP/status in the authoritative encounter state
- **THEN** runtime SHALL resync or refresh the in-memory non-player queue state before the next target lookup or turn-progression decision
- **AND** defeated enemies SHALL be skipped by subsequent target resolution and turn advancement

#### Scenario: Initiative UI reads stale alive status for enemy at zero HP
- **WHEN** a non-player combatant has `currentHitPoints <= 0` even if its stale status still reads `alive`
- **THEN** `initiative_data_response` SHALL exclude that combatant from visible non-player initiative entries
- **AND** player visibility rules for unconscious/incapacitated PCs SHALL remain unchanged

### Requirement: Local Combat Commands SHALL Not Regress Defeated Enemy Truth
Fast-lane local combat commands SHALL preserve Python-applied enemy defeat truth even when later same-turn narration or encounter updates also reference that enemy.

#### Scenario: /dmg defeats enemy before narration follow-up
- **WHEN** `/dmg` reduces an enemy to `0` HP and sets a non-living state locally
- **THEN** subsequent same-turn combat processing SHALL preserve that enemy as defeated
- **AND** runtime SHALL not re-expose that enemy as a living target or visible living initiative combatant during the same encounter turn

#### Scenario: Player attacks enemy after authoritative defeat
- **WHEN** a player uses `/att` against an enemy that has already reached authoritative defeated state in the current encounter
- **THEN** runtime SHALL reject the target as no longer valid
- **AND** the system SHALL not leave the rejected enemy visible in initiative as though still alive

### Requirement: Defeated-Enemy Sync SHALL Preserve Existing Combat Compatibility
The defeated-enemy sync fix SHALL preserve single-player compatibility, current multi-PC phase semantics, and legacy encounter readability.

#### Scenario: Single-player encounter uses existing enemy defeat flow
- **WHEN** combat runs in single-player mode without multi-PC queue helpers
- **THEN** enemy defeat normalization SHALL remain backward compatible with existing encounter persistence behavior
- **AND** the change SHALL not require tabletop-only runtime state to produce correct enemy defeat truth

#### Scenario: Combat round continues after one enemy is defeated
- **WHEN** one enemy is normalized to defeated state while other living combatants remain in the encounter
- **THEN** runtime SHALL preserve the remaining initiative order and active phase semantics for surviving combatants
- **AND** only the defeated combatant SHALL be removed from living-target and visible non-player initiative consideration
