## 1. Runtime authority contracts

- [x] 1.1 Add proposal, design, and spec artifacts for hidden NPC lookup, plot status normalization, and plot-driven location reconciliation
- [x] 1.2 Validate the OpenSpec change reaches apply-ready status

## 2. Hidden NPC and plot normalization implementation

- [x] 2.1 Extend `moveBackgroundNPC` lookup to search hidden/revealable authored NPC identities from area investigation hooks
- [x] 2.2 Add canonical plot-status normalization in the action and persistence paths while preserving schema vocabulary

## 3. Location reconciliation implementation

- [x] 3.1 Add deterministic plot-driven location reconciliation helper using active-module plot/location metadata
- [x] 3.2 Wire inferred `updatePartyTracker` injection into the existing main runtime reconciliation flow without overriding explicit location actions

## 4. Verification

- [x] 4.1 Add or extend regression tests for hidden NPC lookup, plot status normalization, and plot-driven location sync
- [x] 4.2 Run targeted compile/test/OpenSpec validation gates and record outcomes
