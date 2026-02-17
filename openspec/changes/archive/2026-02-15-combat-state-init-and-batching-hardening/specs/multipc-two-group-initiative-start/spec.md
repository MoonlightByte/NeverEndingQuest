## MODIFIED Requirements

### Requirement: Two-group Phase 1 initiative SHALL be authoritative at combat startup
Multi-PC combat startup SHALL enforce Phase 1 two-group initiative state (`dmGroup` vs `pcGroup`) for active encounters.

#### Scenario: New encounter startup
- **WHEN** a new multi-PC encounter starts
- **THEN** initiative startup fields are present and coherent (`initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, `awaitingPcGroupRoll`)
- **AND** `/init <1-20>` is the required gate while awaiting PC group roll

#### Scenario: Startup normalization for partially populated encounter
- **WHEN** an encounter is active but missing one or more Phase 1 initiative fields
- **THEN** runtime normalization fills required missing fields safely
- **AND** does not overwrite valid in-progress round state

### Requirement: Initiative resolution SHALL not regress to legacy per-PC startup flow
After Phase 1 gate resolution, the system SHALL keep two-group initiative progression authoritative for that encounter.

#### Scenario: `/init` resolves winner
- **WHEN** PC group roll is accepted and winner is resolved
- **THEN** encounter and compatibility mirror initiative state are updated coherently
- **AND** startup does not fall back to legacy per-PC initiative collection prompts
