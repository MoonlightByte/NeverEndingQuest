## 0. Execution Guardrails (Mandatory)

- [ ] 0.1 Follow commit order exactly (C1 -> C2 -> C3 -> C4 -> C5). Do not combine scopes.
- [ ] 0.2 Keep edits minimal and localized; only touch files listed under each commit scope.
- [ ] 0.3 Mark new host-file hooks with `# TABLETOP MODE:` comments for merge safety.
- [ ] 0.4 Use ASCII-only output and messages.
- [ ] 0.5 Before opening the next commit, run the required verification for the current commit.

## C1. Combat Entry Fail-Closed (Root Cause)

**Allowed files:**
- `main.py`
- `core/ai/action_handler.py`

**Required changes:**
- [ ] C1.1 In `main.py`, remove fail-open behavior where invalid responses are executed after validation retries are exhausted.
- [ ] C1.2 In `core/ai/action_handler.py`, ensure all `createEncounter` failure paths return explicit error status (no silent continue path).
- [ ] C1.3 Ensure caller path surfaces a deterministic system-visible error when encounter initialization fails.

**Acceptance checks:**
- [ ] C1.A1 No code path executes invalid combat response as canonical progression after retry exhaustion.
- [ ] C1.A2 Encounter init failure does not continue normal combat narration flow.

**Verify before C2:**
- [ ] C1.V1 `python3 -m py_compile main.py core/ai/action_handler.py`

## C2. Combat-Only Command Routing Guards

**Allowed files:**
- `main.py`

**Required changes:**
- [ ] C2.1 Add narrative-loop guards for combat-only commands: `/init`, `/end`, `/att`, `/dmg`, plus existing alias variants in current code.
- [ ] C2.2 If no active encounter exists, intercept command before narrator generation.
- [ ] C2.3 Return deterministic system guidance (non-LLM dependent text path).

**Acceptance checks:**
- [ ] C2.A1 `/init 13` outside combat does not reach narrator lane.
- [ ] C2.A2 `/end` outside combat does not emit farewell/exit narration from LLM.

**Verify before C3:**
- [ ] C2.V1 `python3 -m py_compile main.py`

## C3. Phase 1 Two-Group Initiative Consistency

**Allowed files:**
- `core/managers/combat_manager.py`
- `core/ai/action_handler.py` (only if mirror-sync adjustment is required)

**Required changes:**
- [ ] C3.1 Add/adjust startup normalization so active encounters expose coherent Phase 1 fields (`initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, `awaitingPcGroupRoll`).
- [ ] C3.2 Ensure normalization is safe for in-progress encounters (do not reset valid round state).
- [ ] C3.3 Ensure `/init` resolution updates encounter state and compatibility mirror state coherently.

**Acceptance checks:**
- [ ] C3.A1 Active combat always follows one authoritative two-group startup path.
- [ ] C3.A2 No fallback into legacy per-PC initiative collection after `/init` resolution.

**Verify before C4:**
- [ ] C3.V1 `python3 -m py_compile core/managers/combat_manager.py core/ai/action_handler.py`

## C4. Enemy/NPC Batch Integrity and PC Targeting

**Allowed files:**
- `core/managers/multi_pc_combat.py`
- `core/managers/combat_manager.py`
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (only if wording fix is needed)

**Required changes:**
- [ ] C4.1 Make enemy-phase batch actor list deterministic for all valid living non-PC actors in phase scope.
- [ ] C4.2 Update combatant integrity validation so legal PC target updates during enemy phase are accepted.
- [ ] C4.3 Preserve invariant: PCs forbidden as DM-controlled actors, valid as targets.
- [ ] C4.4 Clarify required prompt/rule wording where necessary to reinforce actor-vs-target distinction.

**Acceptance checks:**
- [ ] C4.A1 Enemy phase can legally apply damage updates to non-active PCs.
- [ ] C4.A2 Integrity checks do not false-reject legal PC target updates.

**Verify before C5:**
- [ ] C4.V1 `python3 -m py_compile core/managers/multi_pc_combat.py core/managers/combat_manager.py`

## C5. Regression Tests and End-to-End Verification

**Allowed files:**
- `scripts/test_multi_pc_combat.py`
- new focused regression test files under `scripts/` (if needed)
- minimal test harness adjustments in touched runtime files from C1-C4

**Required changes:**
- [ ] C5.1 Add/extend regression tests for C1-C4 behaviors.
- [ ] C5.2 Add a test for command guard behavior outside active combat.
- [ ] C5.3 Add a test for fail-closed retry exhaustion behavior.
- [ ] C5.4 Add a test for enemy-phase legal PC targeting through integrity path.

**Mandatory verification commands:**
- [ ] C5.V1 `python3 -m py_compile main.py core/ai/action_handler.py core/managers/combat_manager.py core/managers/multi_pc_combat.py`
- [ ] C5.V2 `python3 scripts/test_multi_pc_combat.py`
- [ ] C5.V3 Run focused new regression tests (if added)

## Manual Smoke Checklist (Release Gate)

- [ ] M1 Force encounter init failure and confirm deterministic system error with no fake combat continuation.
- [ ] M2 In non-combat mode, run `/init 13` and `/end`; confirm command guard responses and no narrator drift.
- [ ] M3 Start real combat and resolve `/init <1-20>`; confirm two-group winner and phase behavior.
- [ ] M4 Run to enemy phase (`/end`) and confirm enemy/NPC actions can damage PCs with proper updates.
- [ ] M5 Confirm no regression in normal PC turn flow (`/att`, `/dmg`) once combat is active.
