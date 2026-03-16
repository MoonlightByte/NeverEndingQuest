# Executor Prompts: npc-scene-presence-reconcile-first

## Execution Contract

MUST:
- Keep G3 narrowly scoped to NPC scene presence.
- Preserve explicit `updatePartyNPCs` for durable join behavior.
- Preserve ambiguity fail-safe behavior.
- Keep host-file edits additive and mark required host hooks with `# TABLETOP MODE:` comments.
- Keep Python output ASCII-only.
- Use transcript-driven tests before runtime behavior changes.
- Stop and report if implementation pressure expands into event-ledger semantics, broad prompt rewrites, or full validator redesign.

SHOULD:
- Prefer narrow deterministic classification over prose-heavy heuristics.
- Treat scene presence, foreshadowing, and party membership as separate outcomes.
- Keep multi-NPC reconciliation out of scope unless one-NPC cases prove insufficient.

## Prompt 1 - Transcript Locks First (Tasks 1.1-1.4)

Implement the new G3 regression tests before changing runtime behavior.

Scope:
- Add transcript-driven tests for:
  1. the Maelo-style scene-presence loop that should reconcile later,
  2. foreshadowing/informational references that remain legal,
  3. explicit join language that must still require `updatePartyNPCs`,
  4. ambiguous identity that must not auto-commit.
- Prefer deterministic unit tests over broad end-to-end fixtures.
- It is acceptable at this stage for the new reconcile-first expectation test to fail before runtime implementation.

Verification gate before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run the new G3 test file and record which failures are expected pre-implementation.

## Prompt 2 - Runtime Classification Narrowing (Tasks 3.1-3.4)

After review, implement the smallest reconcile-first scene-presence behavior.

Scope:
- Update `utils/npc_arrival_validator.py` to classify:
  - foreshadowing / informational mention,
  - clear scene presence,
  - explicit party join,
  - ambiguous identity.
- Update `main.py` to reconcile clear scene presence instead of immediately failing.
- Preserve explicit action precedence.

Constraints:
- Do not equate scene presence with party membership.
- Do not infer durable joins from flavor narration.
- Do not broaden into generic NPC world movement tracking.

Verification gate before continuing:
- `python3 -m py_compile main.py utils/npc_arrival_validator.py <changed_test_files>`
- Run the G3 tests plus touched NPC/retry regressions.

## Prompt 3 - Final Verification and Report (Tasks 4.1-4.4)

Required checks:
- `python3 -m py_compile main.py utils/npc_arrival_validator.py core/ai/action_handler.py <changed_test_files>`
- Run the new G3 tests
- Run existing NPC arrival and retry-loop regressions
- `openspec validate npc-scene-presence-reconcile-first`

Report format:
- Files changed
- Commands run
- PASS/FAIL per gate
- Which scene-presence cases reconcile
- Which cases still remain explicit-only or fail-safe by design
