## 1. Encounter Defeat Normalization

- [x] 1.1 Add a focused enemy-state normalization helper in `updates/update_encounter.py` that clamps non-player enemy HP to `0` minimum and assigns a schema-legal non-living status when HP resolves to `0` or below.
- [x] 1.2 Route both supported-op and fallback encounter update paths through the same enemy defeat normalization/finalization logic so persisted encounter files cannot keep `currentHitPoints <= 0` with `status = alive`.
- [x] 1.3 Add targeted regression coverage for negative-HP enemy persistence normalization and run the relevant encounter update test(s).

## 2. Queue and Target Sync

- [x] 2.1 Add a narrow non-PC queue resync helper in `core/managers/multi_pc_combat.py` or `core/managers/combat_manager.py` that refreshes enemy/NPC HP and status from authoritative `encounter_data` without disturbing active PC ownership.
- [x] 2.2 Invoke that resync immediately after `updateEncounter` mutations in `core/managers/combat_manager.py` so targeting and turn progression use the corrected enemy state during the same combat turn.
- [x] 2.3 Add regression coverage proving defeated enemies are skipped by subsequent target resolution and turn progression after an immediate encounter-state update.

## 3. Initiative UI Coherence

- [x] 3.1 Update `web/extensions/tabletop_socket_handlers.py` so non-player initiative entries are hidden when enemy status is non-living or `currentHitPoints <= 0`, while preserving current player visibility rules for unconscious/incapacitated PCs.
- [x] 3.2 Add source-contract or runtime regression coverage for the initiative payload so defeated enemies no longer appear as living visible combatants.

## 4. Fast-Lane Damage Hardening

- [x] 4.1 Audit the fast-lane `/dmg` flow in `core/managers/multi_pc_combat.py` and `core/managers/combat_manager.py` so Python-applied enemy defeat state remains authoritative during the same-turn narration follow-up.
- [x] 4.2 Add a guard or normalization step that prevents same-turn narration-side encounter updates from re-exposing a locally defeated enemy as alive or targetable.
- [x] 4.3 Add focused regression coverage for `/dmg` defeating an enemy followed by narration/update processing, verifying no ghost enemy remains in targeting or initiative UI.

## 5. Verification

- [x] 5.1 Run `python3 -m py_compile` on all modified combat and web files touched by this change.
- [x] 5.2 Run the targeted combat regression suites covering encounter updates, multi-PC combat targeting, and initiative payload behavior.
- [ ] 5.3 Perform a manual smoke check for `/att`, `/dmg`, and defeated-enemy visibility during a live combat turn; verify the enemy disappears from valid targets and non-player initiative once authoritatively defeated.
