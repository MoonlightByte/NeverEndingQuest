# Tasks: tt-transition-time-failopen-sync

## 1. Runtime Fail-Open Fallback

- [x] 1.1 Add a focused helper in `main.py` (or adjacent runtime utility) to detect a response bundle containing `transitionLocation` and missing `updateTime`.
- [x] 1.2 Inject one deterministic synthetic `updateTime` action when missing:
  - same-area transition => 10 minutes
  - cross-area transition => 20 minutes
- [x] 1.3 Ensure fallback runs only once per response and never when `updateTime` already exists.
- [x] 1.4 Add ASCII log line for observability: `STATE_SYNC: Auto-applied updateTime=<N> due to transitionLocation without updateTime`.

## 2. Prompt + Validation Contract Reinforcement

- [x] 2.1 Update `prompts/system_prompt_compressed.txt` travel guidance to explicitly require `transitionLocation` + `updateTime` pairing in same response.
- [x] 2.2 Update `prompts/validation/validation_prompt_compressed.txt` with missing-pair violation language and valid bundle example.
- [x] 2.3 Update `prompts/validation/validation_prompt.txt` with equivalent uncompressed rules/examples.

## 3. Regression Coverage

- [x] 3.1 Add/extend tests for fallback injection when `transitionLocation` lacks `updateTime`.
- [x] 3.2 Add/extend tests proving no double-update when explicit `updateTime` is already present.
- [x] 3.3 Add/extend tests proving non-transition turns are unchanged.

## 4. Verification

- [x] 4.1 `python3 -m py_compile main.py` -> COMPILE OK
- [x] 4.2 `python3 -m py_compile` on any new/modified test files -> COMPILE OK
- [x] 4.3 Run targeted regression tests added/updated for this change -> 8/8 PASS
- [x] 4.4 `openspec validate tt-transition-time-failopen-sync` -> VALID
