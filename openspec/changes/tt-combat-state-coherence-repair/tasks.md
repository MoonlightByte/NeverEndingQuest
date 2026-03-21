## 1. Combat Identity Normalization

- [x] 1.1 Add canonical party-member dedupe at multi-PC combat initialization/resume in `core/managers/multi_pc_combat.py` so mixed-form party labels create one logical PC combatant.
- [x] 1.2 Update player combatant backfill and player-phase initiative summary generation to exclude duplicate canonical PCs and stale dead-enemy leakage from player-facing turn windows.
- [x] 1.3 Add regression coverage for duplicate mixed-form party members (`xorn`/`Xorn`, `athelon`/`Athelon`, `lidda_underbough`/`Lidda Underbough`) and verify one logical combatant per canonical PC.

## 2. Active-Turn Coherence and Target Selection

- [x] 2.1 Reconcile selected active PC, prompt actor, and player-phase required-response generation in `core/managers/combat_manager.py` and `core/managers/multi_pc_combat.py` so manual switching cannot emit a stale actor contract.
- [x] 2.2 Harden local `/att` and `/dmg` target resolution in `core/managers/multi_pc_combat.py` to prefer living canonical matches and reject defeated-only matches.
- [x] 2.3 Add regression coverage for manual active-PC switching, stale queue actor prevention, and living-target preference over dead same-family enemies.

## 3. Incapacitated Turn and Death-Save Persistence

- [x] 3.1 Add additive schema support for durable death-save state in `schemas/char_schema.json` and align any affected validation helpers.
- [x] 3.2 Extend deterministic character ops handling in `updates/update_character_info.py` to persist death-save success/failure updates without silent purge or prose fallback loss.
- [x] 3.3 Add incapacitated-command guards in fast-lane combat handling so unconscious PCs cannot use normal `/att` or `/dmg` actions and are routed into death-save flow instead.
- [x] 3.4 Ensure `requestRoll` death-save turns resume into deterministic persistence and crash/recovery-safe character state updates.
- [x] 3.5 Add regression coverage for death-save request, failed-save persistence, and resumed combat preserving existing death-save counters.

## 4. Verification

- [x] 4.1 Run targeted syntax checks for touched Python and JSON files.
- [x] 4.2 Run focused combat regression suites covering duplicate-PC roster coherence, active-turn sync, dead-target rejection, and death-save persistence.
- [x] 4.3 Document any follow-up risks or SHOULD-level cleanup discovered during implementation in the change notes before marking the change apply-ready.
