# Executor Prompts: travel-reconcile-first-autocommit

## Execution Contract

MUST:
- Implement this change as a travel-only gametest slice.
- Preserve the current JSON/action schema surface.
- Preserve explicit `transitionLocation` behavior as a preferred supported path.
- Keep same-location and impossible-topology travel blocked.
- Keep Python output ASCII-only.
- Keep host-file edits additive and mark required host hooks with `# TABLETOP MODE:` comments.
- Use anchored, micro-edits in `main.py` and any large Python file.
- Run `python3 -m py_compile <changed_python_file>` after each touched Python file.
- Stop and report if implementation pressure expands into broad NPC presence, prompt-stack, or validator-rewrite scope.

SHOULD:
- Build on `narrative-sovereignty-state-packet-foundation` if that change is already implemented.
- If packet foundation is not yet implemented, keep travel inputs narrow and compatibility-safe so packet adoption remains straightforward later.
- Prefer additive travel reconciliation over deletion of the existing explicit transition path.
- Keep transcript tests close to the motivating gametest failures.

## Prompt 1 - Transcript and Contract Coverage First (Tasks 1.1-1.4)

Implement the travel regression suite before changing runtime behavior.

Scope:
- Add tests for:
  1. clear travel intent + explicit narrated arrival + no `transitionLocation` -> legal auto-commit
  2. clear travel intent + progress toward known destination + no exact arrival -> in-transit/progress state commit
  3. clear travel intent + ambiguous destination -> no wrong auto-commit; safe clarify/fail-soft behavior
  4. impossible travel or disconnected destination -> block
  5. same-location travel/no-op -> remains blocked
- Reuse existing travel/validation test patterns where possible.
- Keep fixtures deterministic and focused on runtime contract, not broad integration setup.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification gate before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run the new tests and confirm failures reflect missing travel-reconciliation behavior, not broken fixtures.

## Prompt 2 - Reconcile-First Travel Core (Tasks 2.1-2.4)

Implement the travel auto-commit and in-transit core behavior.

Scope:
- Use travel-intent classification as the activation gate.
- Preserve explicit `transitionLocation` precedence when present.
- Allow runtime to auto-commit legal narrated arrival when destination is safely resolvable.
- Add narrow in-transit/progress state when movement is clear but exact arrival is not yet justified.
- Preserve same-location and impossible-topology hard safety.
- Avoid broad NPC or validator-domain expansion.

Constraints:
- Do not turn this into a general prose parser for all turns.
- Do not auto-commit arbitrary destinations on ambiguous narration.
- Do not break existing explicit transition blocking and same-location stripping behavior.
- Do not remove the old explicit path in this slice.

Likely files:
- `main.py`
- `utils/travel_state_sync_guard.py`
- `core/managers/location_manager.py`
- `core/ai/action_handler.py`
- optionally `utils/authoritative_state_packet.py` only if narrow travel inputs require it and it already exists in the foundation slice

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification gate before continuing:
- `python3 -m py_compile main.py utils/travel_state_sync_guard.py core/managers/location_manager.py core/ai/action_handler.py`
- Run the new travel reconciliation tests.

## Prompt 3 - Travel Time Synchronization for Effective Commits (Task 2.5)

Extend deterministic time synchronization so inferred travel commits keep clock state aligned.

Scope:
- Preserve existing explicit `transitionLocation` + `updateTime` behavior.
- Apply deterministic fallback time for inferred arrival commits.
- Apply deterministic fallback time for in-transit/progress commits.
- Keep non-travel turns unchanged.

Constraints:
- Explicit `updateTime` remains authoritative.
- Do not inject duplicate time actions on explicit valid travel bundles.
- Keep time fallback deterministic and compatible with existing transition-time logic.

Verification gate before continuing:
- `python3 -m py_compile <changed_python_files>`
- Run targeted travel-time and travel-reconciliation regressions.

## Prompt 4 - Validation Narrowing and Prompt Parity Only If Needed (Tasks 3.1-3.2)

Narrow travel-domain validation so legal travel prefers reconciliation over reject-first looping.

Scope:
- Update `main.py` travel-domain validation behavior only as needed to allow legal travel reconciliation.
- Add prompt/validation parity wording only if runtime tests show correction mismatch.
- Keep prompt edits narrow and travel-specific.

Constraints:
- Do not perform a broad validator authority rewrite in this change.
- Do not touch NPC arrival semantics unless required for a travel-only correctness fix and clearly report it.
- Preserve hard blocking for impossible movement.

Likely files:
- `main.py`
- maybe `prompts/system_prompt_compressed.txt`
- maybe `prompts/validation/validation_prompt_compressed.txt`
- mirror uncompressed files only if parity is required

Verification gate before continuing:
- Re-run travel reconciliation tests
- Re-run affected existing travel/validation regressions
- Re-run any source-contract tests affected by prompt wording updates

## Prompt 5 - Final Verification and Builder Report (Tasks 4.1-4.4)

Run final checks and return a concise implementation report.

Required checks:
- `python3 -m py_compile main.py utils/travel_state_sync_guard.py core/managers/location_manager.py core/ai/action_handler.py <changed_test_files>`
- Run targeted travel reconciliation regression tests
- Run affected existing travel/validation regressions
- `openspec validate travel-reconcile-first-autocommit`

Report format:
- Files changed
- Commands run
- PASS/FAIL per verification gate
- Whether packet foundation was consumed directly or left as future-compatible dependency
- Any follow-up concerns before conditional NPC-scene-presence work
