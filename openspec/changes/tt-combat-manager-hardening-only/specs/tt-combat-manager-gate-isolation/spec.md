## ADDED Requirements

### Requirement: `/init` Gate Handling SHALL Be Isolated Behind a TT Helper Contract
The multi-PC two-group initiative gate handling for `/init` SHALL execute through a dedicated helper boundary instead of an inline monolithic branch.

#### Scenario: Valid `/init` request is handled through helper
- **WHEN** combat is awaiting facilitator initiative input and user submits `/init <1-20>`
- **THEN** the helper SHALL validate input, resolve winner (`pcGroup` vs `dmGroup`), and return structured handling output
- **AND** caller flow SHALL continue using helper output without duplicating winner/phase logic inline

#### Scenario: Invalid `/init` request is rejected deterministically
- **WHEN** user submits malformed or out-of-range `/init` input while gate is active
- **THEN** helper SHALL return a deterministic error response
- **AND** combat progression SHALL remain blocked until a valid `/init` is received

### Requirement: Initiative State Writes SHALL Preserve Existing TT Semantics
Helper-based handling SHALL preserve current TT state updates and persistence behavior.

#### Scenario: Winner and marker persistence
- **WHEN** helper resolves initiative winner
- **THEN** encounter state SHALL persist `initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, and `awaitingPcGroupRoll`
- **AND** helper SHALL apply `openingEnemyBatchPending` marker via TT state sync helper

#### Scenario: Compatibility mirror persistence
- **WHEN** helper resolves winner and rolls
- **THEN** party tracker mirror (`worldConditions.combatInitiative`) SHALL be updated consistently with current behavior
- **AND** persistence SHALL use existing safe JSON write paths

### Requirement: TT-Only Refactor Scope SHALL Avoid Upstream Flow Drift
This extraction SHALL remain scoped to TT initiative branches in current test build.

#### Scenario: Single-player behavior remains unchanged
- **WHEN** single-player combat path executes
- **THEN** refactor SHALL not alter single-player initiative/combat flow behavior
- **AND** no TT-only helper branch SHALL be required for SP execution
