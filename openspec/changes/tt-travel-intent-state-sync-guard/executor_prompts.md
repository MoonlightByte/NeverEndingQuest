# Executor Prompts: tt-travel-intent-state-sync-guard

## Execution Contract

MUST:
- Implement only the scoped travel-intent runtime guard and its tests.
- Keep runtime behavior unchanged for non-travel turns.
- Preserve existing same-location stripping, transition pre-validation, and updateTime fallback semantics.
- Keep Python output ASCII-only.
- Use anchored, micro-edits in `main.py`.
- Run `python3 -m py_compile <changed_python_file>` after each touched Python file.
- Stop and report if destination/arrival detection becomes too ambiguous for deterministic enforcement.

SHOULD:
- Reuse existing travel-intent classification and retry-local correction mechanisms.
- Keep detection narrow and explicit rather than building a broad prose parser.
- Add parity prompt edits only if runtime tests prove they are needed.

## Prompt 1 - Tests First (Tasks 1.1-1.4)

Implement focused regression coverage before changing runtime behavior.

Scope:
- Add tests for:
  1. clear travel intent + narrated arrival elsewhere + no `transitionLocation` -> reject
  2. clear travel intent + current-location blocker -> allow without transition
  3. clear travel intent + clarification question -> allow without transition
  4. contradictory dual-location narration in one response -> reject
  5. ambiguous travel-adjacent prose -> fail open
- Keep fixtures minimal and source-contract oriented where possible.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification before continuing:
- `python3 -m py_compile <changed_test_files>`
- Run new tests and confirm they fail for missing implementation behavior, not setup issues.

## Prompt 2 - Runtime Guard (Tasks 2.1-2.3)

Add the deterministic travel-state sync guard in the response validation path.

Scope:
- Use existing travel-intent classification output.
- Detect explicit arrival/entry/emergence into a new location without `transitionLocation`.
- Allow explicit current-location blocker and clarification responses without forcing transitions.
- Reject contradictory mixed-location narration when explicit.
- Reuse retry-local correction path.
- Do not break existing same-location stripping or `pre_validate_transition(...)` flow.

Constraints:
- Fail open on ambiguous prose.
- Do not auto-infer or auto-inject `transitionLocation` from narration.
- Do not append failed travel narration into persistent history.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verification before continuing:
- `python3 -m py_compile main.py`
- Run the new travel-state tests.

## Prompt 3 - Prompt / Validator Parity Only If Needed (Task 3.1)

Only if runtime tests show correction mismatch, update prompt guidance.

Scope:
- Keep edits minimal in `prompts/validation/validation_prompt_compressed.txt` and mirror text if needed.
- Reinforce: travel narration that arrives elsewhere requires `transitionLocation`; blocker/clarifier responses may stay action-free if party remains in current location.
- Avoid broad prompt rewrites.

Verification before continuing:
- Re-run any prompt/source-contract tests touched by the wording update.

## Prompt 4 - Final Verification (Tasks 4.1-4.4)

Run final checks and provide a concise report.

Required checks:
- `python3 -m py_compile main.py <changed_test_files>`
- Run targeted travel-state sync regressions
- Run affected existing travel/validation regressions
- `openspec validate tt-travel-intent-state-sync-guard`

Report format:
- Files changed
- Commands run
- PASS/FAIL per gate
- Any follow-up concerns or ambiguity notes
