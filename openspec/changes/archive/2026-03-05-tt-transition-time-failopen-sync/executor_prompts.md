# Executor Prompts: tt-transition-time-failopen-sync

## Execution Contract

MUST:
- Keep edits scoped to this change.
- Preserve existing behavior outside transition-time sync contracts.
- Use ASCII-only log strings.
- Keep TT changes merge-safe and surgical.
- Run compile checks after Python edits.

SHOULD:
- Prefer one helper function for fallback detection/injection.
- Keep fallback minutes deterministic and centralized.

## Prompt 1 - Runtime Fail-Open Fallback (Tasks 1.1-1.4)

Implement deterministic auto-time fallback when movement occurs without explicit time advancement.

Scope:
- File: `main.py` (or nearest action-processing helper used by the main loop).
- Detect per-response action bundle:
  - has one or more `transitionLocation`
  - has zero `updateTime`
- Inject one synthetic `updateTime` action before non-character actions execute.
- Deterministic fallback minutes:
  - 10 minutes for same-area movement
  - 20 minutes for cross-area movement
- Add ASCII observability log:
  - `STATE_SYNC: Auto-applied updateTime=<N> due to transitionLocation without updateTime`

Constraints:
- Do not alter behavior when explicit `updateTime` already exists.
- Do not apply fallback on non-transition turns.
- Keep action ordering stable beyond inserting the single synthetic `updateTime`.

Verification before continuing:
- `python3 -m py_compile main.py`

## Prompt 2 - Prompt + Validation Contract Reinforcement (Tasks 2.1-2.3)

Update prompt contracts to require travel bundles.

Scope:
- `prompts/system_prompt_compressed.txt`
- `prompts/validation/validation_prompt_compressed.txt`
- `prompts/validation/validation_prompt.txt`

Requirements:
- State that movement transitions SHOULD include `updateTime` in same response.
- Add one valid bundled example and one missing-pair violation pattern in validator prompts.
- Keep wording consistent with existing action schema rules.

## Prompt 3 - Regression Coverage + Final Verification (Tasks 3.1-4.4)

Add or extend targeted tests.

Required test assertions:
- Missing `updateTime` with transition triggers exactly one synthetic `updateTime`.
- Existing transition+updateTime bundle remains unchanged (no duplicate time update).
- Non-transition action bundles remain unchanged.

Run:
- `python3 -m py_compile main.py`
- `python3 -m py_compile <updated_test_files>`
- targeted tests for this change
- `openspec validate tt-transition-time-failopen-sync`

Report:
- files changed
- tests and command outputs
- PASS/FAIL by gate
