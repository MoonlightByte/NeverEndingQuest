# tt-combat-manager-gate-isolation Specification

## Purpose
TBD - created by archiving change tt-combat-manager-hardening-only. Update Purpose after archive.
## Requirements
### Requirement: `/init` Gate Handling SHALL Be Isolated Behind a TT Helper Contract
The multi-PC two-group initiative gate handling for `/init` SHALL execute through a dedicated helper boundary instead of an inline monolithic branch.

#### Scenario: Valid `/init` request is handled through helper
- **WHEN** combat is awaiting facilitator initiative input and user submits `/init <1-20>`
- **THEN** the helper SHALL validate input, resolve winner (`pcGroup` vs `dmGroup`), and return structured handling output
- **AND** caller flow SHALL continue using helper output without duplicating winner/phase logic inline

#### Scenario: dmGroup winner preserves forced enemy-turn fall-through behavior
- **WHEN** helper resolves `dmGroup` as winner (including ties)
- **THEN** helper-driven handling SHALL preserve current behavior that sets ENEMY phase state and triggers enemy-turn fall-through handling in caller flow
- **AND** deterministic gate output contract SHALL remain compatible with existing `[skipTTS][prefill:/init ]` guidance behavior for invalid/non-`/init` gate input

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

#### Scenario: Existing marker lifecycle remains intact after extraction
- **WHEN** round-start handling or opening-batch completion runs after helper extraction
- **THEN** opening marker semantics SHALL remain unchanged across `/init` resolution, round-start reapplication, and post-opening-batch clear transition back to PC phase

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

### Requirement: Phase1 Normalization Ownership SHALL Remain Stable In This Change
This hardening change SHALL preserve the current ownership split for phase1 initiative normalization and TT sync helpers.

#### Scenario: No relocation of phase1 normalization in this change
- **WHEN** this refactor is implemented
- **THEN** `normalize_phase1_initiative(...)` SHALL remain in `core/managers/combat_manager.py`
- **AND** `core/managers/combat_state_sync.py` SHALL continue owning marker/roster helper responsibilities without taking over phase1 normalization in this change

