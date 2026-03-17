## 1. Durable Ownership Guard

- [x] 1.1 Add a tabletop-only active-combat ownership helper in `core/ai/action_handler.py` that checks `party_tracker.json -> worldConditions.activeCombatEncounter` before allowing `createEncounter` to start a new unresolved encounter.
- [x] 1.2 Make duplicate tabletop encounter startup fail closed with explicit structured status and a concise player-visible `[SYSTEM]` message path, without changing successful create/start behavior.

## 2. Runtime Session Claim

- [x] 2.1 Add a process-local single-session claim/release helper in `core/managers/combat_manager.py` so `run_combat_simulation(...)` rejects concurrent startup and always releases ownership on exit.
- [x] 2.2 Add a narrow coherence check so runtime startup prefers the durable active encounter owner and logs a deterministic diagnostic when history/runtime startup attempts drift to a different encounter id.

## 3. Regression Coverage And Verification

- [x] 3.1 Extend `scripts/c5_regression_combat.py` or `scripts/test_multi_pc_combat.py` with focused coverage for duplicate encounter creation rejection, concurrent combat-loop startup rejection, and preserved happy-path `/init` -> `/att` flow.
- [x] 3.2 Verify with `python3 -m py_compile core/ai/action_handler.py core/managers/combat_manager.py` plus targeted combat regressions demonstrating that only one encounter owns input at a time.

SHOULD: keep edits micro-scoped, prefer helper extraction over deep branch rewrites, and avoid prompt-file changes unless verification proves a code-only guard is insufficient.
