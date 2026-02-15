## Kimi/GLM Executor Prompts

Use these prompts as strict step-by-step execution guardrails.

Execution policy:
- Run one commit slice at a time (`C1` -> `C5`).
- Do not touch files outside each slice's allowed scope.
- Run required verification for the current slice.
- Stop and wait for human approval before the next slice.

---

## 0) Session Bootstrap Prompt (Run First)

```text
You are implementing OpenSpec change: combat-state-init-and-batching-hardening.

Rules you MUST follow:
1) Read these files first and treat them as source of truth:
   - openspec/changes/combat-state-init-and-batching-hardening/tasks.md
   - openspec/changes/combat-state-init-and-batching-hardening/proposal.md
   - openspec/changes/combat-state-init-and-batching-hardening/design.md
2) Execute exactly one commit slice at a time (C1, then stop).
3) For each slice, edit only allowed files listed in tasks.md.
4) If a needed change appears outside allowed files, STOP and report blocker.
5) Run required verify commands for the slice and report full status.
6) Do not start next slice without explicit human approval.
7) Preserve TABLETOP MODE comments in host file modifications.
8) Keep output ASCII-only.

Output format:
- Slice: <C1|C2|...>
- Files changed: <list>
- What changed: <bullets>
- Verification run: <commands and PASS/FAIL>
- Blockers: <none or details>
- Ready for next slice: <yes/no>

Acknowledge and wait for: "Run C1".
```

---

## 1) C1 Prompt - Combat Entry Fail-Closed

```text
Run C1 only for OpenSpec change combat-state-init-and-batching-hardening.

Scope lock (allowed files only):
- main.py
- core/ai/action_handler.py

Required C1 tasks:
- C1.1 Remove fail-open behavior where invalid responses execute after validation retry exhaustion.
- C1.2 Ensure createEncounter failure paths return explicit error status (no silent continue).
- C1.3 Surface deterministic system-visible error for failed encounter initialization.

Acceptance criteria:
- C1.A1 No path executes invalid combat response as canonical progression after retry exhaustion.
- C1.A2 Encounter init failure does not continue normal combat narration flow.

Required verification:
- python3 -m py_compile main.py core/ai/action_handler.py

Do NOT run C2. Stop after C1 report.

Output format:
- Slice: C1
- Files changed:
- Diff summary:
- Acceptance check mapping (C1.A1/C1.A2):
- Verification output:
- Ready for human review: yes
```

---

## 2) C2 Prompt - Combat Command Routing Guards

```text
Run C2 only for OpenSpec change combat-state-init-and-batching-hardening.

Precondition:
- C1 already completed and approved.

Scope lock (allowed files only):
- main.py

Required C2 tasks:
- C2.1 Add narrative-loop guards for combat-only commands: /init, /end, /att, /dmg, plus existing alias variants.
- C2.2 Intercept before narrator generation when no active encounter exists.
- C2.3 Return deterministic non-LLM system guidance.

Acceptance criteria:
- C2.A1 /init outside combat does not reach narrator lane.
- C2.A2 /end outside combat does not emit LLM farewell/exit narration.

Required verification:
- python3 -m py_compile main.py

Do NOT run C3. Stop after C2 report.
```

---

## 3) C3 Prompt - Two-Group Initiative Consistency

```text
Run C3 only for OpenSpec change combat-state-init-and-batching-hardening.

Precondition:
- C2 already completed and approved.

Scope lock (allowed files only):
- core/managers/combat_manager.py
- core/ai/action_handler.py (only if mirror-sync adjustment is required)

Required C3 tasks:
- C3.1 Normalize startup initiative fields for Phase 1 two-group flow.
- C3.2 Do not reset valid in-progress encounter round state.
- C3.3 Ensure /init resolution updates encounter + compatibility mirror coherently.

Acceptance criteria:
- C3.A1 Single authoritative two-group startup path.
- C3.A2 No fallback into legacy per-PC initiative collection after /init resolution.

Required verification:
- python3 -m py_compile core/managers/combat_manager.py core/ai/action_handler.py

Do NOT run C4. Stop after C3 report.
```

---

## 4) C4 Prompt - Enemy/NPC Batch Integrity and PC Targeting

```text
Run C4 only for OpenSpec change combat-state-init-and-batching-hardening.

Precondition:
- C3 already completed and approved.

Scope lock (allowed files only):
- core/managers/multi_pc_combat.py
- core/managers/combat_manager.py
- prompts/combat/combat_sim_prompt_multipc_compressed.txt (only if wording fix is needed)

Required C4 tasks:
- C4.1 Deterministic enemy-phase actor list for valid living non-PC actors.
- C4.2 Integrity validation accepts legal PC target updates in enemy phase.
- C4.3 Preserve invariant: PCs forbidden as DM-controlled actors, valid targets.
- C4.4 Clarify prompt wording only if needed.

Acceptance criteria:
- C4.A1 Enemy phase can apply damage updates to non-active PCs.
- C4.A2 Integrity checks do not false-reject legal PC target updates.

Required verification:
- python3 -m py_compile core/managers/multi_pc_combat.py core/managers/combat_manager.py

Do NOT run C5. Stop after C4 report.
```

---

## 5) C5 Prompt - Regression and Release Gate

```text
Run C5 only for OpenSpec change combat-state-init-and-batching-hardening.

Precondition:
- C4 already completed and approved.

Scope lock (allowed files only):
- scripts/test_multi_pc_combat.py
- new focused regression tests under scripts/ (if needed)
- minimal test harness updates in runtime files touched by C1-C4 only

Required C5 tasks:
- C5.1 Add/extend regressions for C1-C4 behaviors.
- C5.2 Add command-guard tests outside active combat.
- C5.3 Add fail-closed retry exhaustion test.
- C5.4 Add legal PC-target enemy-phase integrity test.

Required verification:
- python3 -m py_compile main.py core/ai/action_handler.py core/managers/combat_manager.py core/managers/multi_pc_combat.py
- python3 scripts/test_multi_pc_combat.py
- run any newly added focused tests

Manual smoke checklist (must report pass/fail item-by-item):
- M1 force encounter init failure -> deterministic system error, no fake combat continuation
- M2 /init and /end outside combat -> guarded, deterministic responses
- M3 start combat and resolve /init -> two-group winner path works
- M4 enemy phase /end -> enemy/NPC actions can damage PCs correctly
- M5 normal PC turn flow in active combat still works

Stop and provide final report only. Do not archive change.
```

---

## 6) Review Prompt (Human Validation Pass)

```text
Produce a strict traceability report for combat-state-init-and-batching-hardening.

For each task in tasks.md:
- show implementation status (done/partial/not done)
- show exact file and function touched
- show verification evidence (command + pass/fail)

For each requirement in specs/*/spec.md:
- map to code and/or tests
- if unmet, list exact gap and minimal fix

Output sections:
1) Task completion matrix
2) Requirement-to-code mapping
3) Verification evidence
4) Outstanding risks
5) Go/No-Go recommendation
```
