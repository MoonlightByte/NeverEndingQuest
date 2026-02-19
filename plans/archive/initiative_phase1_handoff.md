# Phase 1 Initiative Handoff (Session Resume Guide)

Status: IN PROGRESS
Scope: Two-group initiative only (`dmGroup` vs `pcGroup`), merge-safe TT hooks in core files.

## What is already implemented

1. Encounter startup state creation in `core/ai/action_handler.py`
   - Added Phase 1 fields to encounter JSON on combat creation:
     - `initiativeMode: "two_group_phase1"`
     - `initiativeRolls: {"dmGroup": <d20>, "pcGroup": null}`
     - `initiativeWinner: null`
     - `roundStartsWith: null`
     - `awaitingPcGroupRoll: true`
   - Added `random` import and DM pre-roll generation.
   - Kept legacy mirror in `party_tracker.json -> worldConditions.combatInitiative` for compatibility.

2. `/init` gate and parsing in `core/managers/combat_manager.py`
   - Added hard gate when `awaitingPcGroupRoll` is true.
   - Only `/init <1-20>` is accepted; all other input blocked with usage hint.
   - Valid `/init` writes:
     - `initiativeRolls.pcGroup`
     - `initiativeWinner`
     - `roundStartsWith`
     - `awaitingPcGroupRoll = false`
   - Tie rule enforced: `dmGroup` wins ties.
   - If `dmGroup` wins, enemy phase is immediately triggered via injected system message.
   - Added help command line: `/init [1-20] - Set PC group initiative roll`.

3. Dynamic initiative context + deterministic round start in `core/managers/combat_manager.py`
   - Added prompt context block:
     - `=== INITIATIVE STATE ===`
     - `MODE`, `DM_GROUP_ROLL`, `PC_GROUP_ROLL`, `WINNER`, `ROUND_STARTS_WITH`, `CURRENT_PHASE`
   - At round advancement, phase now starts from `roundStartsWith`:
     - `dmGroup` => enemy phase start
     - `pcGroup` => PC phase start

## Verification completed so far

- `python3 -m py_compile core/ai/action_handler.py` -> PASS
- `python3 -m py_compile core/managers/combat_manager.py` -> PASS

## Remaining work (execute in order)

### Step 4: Prompt wording updates (minimal)

Files:
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`

Required edits:
1. Simulation prompt: allow ENEMY_PHASE to start by initiative winner (not only `/end`).
2. Validation prompt: treat initiative-driven ENEMY_PHASE start as valid when initiative state indicates DM starts.
3. Keep changes additive and short; do not rewrite prompt structure.

Acceptance criteria:
- Prompt text clearly supports initiative-driven phase entry.
- Existing `/end` batch semantics remain documented and intact.

### Step 5: Validate behavior and regressions

Run checks:
1. `python3 -m py_compile core/ai/action_handler.py core/managers/combat_manager.py`
2. `python3 scripts/test_multi_pc_combat.py`

Manual scenario checks:
1. DM win: `/init` lower than DM roll -> first phase ENEMY_PHASE.
2. PC win: `/init` higher than DM roll -> first phase PC_PHASE.
3. Tie: equal rolls -> DM wins tie.
4. Invalid `/init` (`abc`, `0`, `21`, missing arg) -> blocked and prompted.
5. Round N+1 starts from `roundStartsWith` consistently.
6. `/end` still hands off to enemy batch exactly as before.

## Merge-safety notes

- Core hooks are marked with `# TABLETOP MODE:` and inserted at existing control points.
- No major host feature restructuring performed.
- The implementation remains additive and should be conflict-local during upstream sync.

## Current local workspace state (for awareness)

`git status --short` at handoff time:
- `M .gitignore` (pre-existing/unrelated)
- `M core/ai/action_handler.py` (this work)
- `M core/managers/combat_manager.py` (this work)
- `?? data/world_surveillance.db` (untracked/unrelated)
