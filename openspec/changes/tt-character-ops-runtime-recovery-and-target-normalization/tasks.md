## 1. Target normalization foundation

- [x] 1.1 Add shared canonical target-identity helper(s) for structured character ops matching, covering case, spacing, punctuation, apostrophes, hyphens, and compacted aliases.
- [x] 1.2 Update deterministic target lookup in `updates/update_character_info.py` for class features to prefer exact match, then canonical identity match, then conservative loose match.
- [x] 1.3 Extend the same canonical lookup strategy to supported inventory and ammunition target matching paths where label drift can currently produce false unknown-target failures.
- [x] 1.4 Review and harden adjacent structured-op normalization helpers in `utils/character_ops_routing.py` so legacy wrapper normalization stays aligned with the supported op set.

## 2. Apply-time recovery routing

- [x] 2.1 Introduce a recoverable-vs-authoritative deterministic apply failure classifier in `updates/update_character_info.py`.
- [x] 2.2 Update mixed `changes + ops` runtime handling so recoverable deterministic apply failures degrade to the prose `changes` path when safe fallback exists.
- [x] 2.3 Preserve fail-closed behavior for authoritative contradictions such as underflow, overflow, impossible removals, and invalid death-save mutations.
- [x] 2.4 Convert deterministic apply exceptions and invalid numeric/shape errors into structured routing outcomes instead of opaque generic failures.

## 3. User-facing recovery and observability

- [x] 3.1 Update `core/ai/action_handler.py` to preserve specific routing/error outcomes for recoverable degradation versus authoritative block cases.
- [x] 3.2 Update `main.py` character-update error surfacing so recoverable cases do not emit opaque generic `Unknown error in character update` messages.
- [x] 3.3 Keep or extend deterministic routing markers/diagnostics so degraded fallback outcomes remain visible to regression tests and debug logs.

## 4. Regression coverage

- [x] 4.1 Extend structured character ops tests for class feature alias normalization cases such as `DivineSense`, `LayonHands`, and other compacted feature labels.
- [x] 4.2 Add runtime recovery regressions for mixed payloads where recoverable deterministic apply failures fall back to prose successfully.
- [x] 4.3 Add hard-fail regressions proving authoritative contradictions still remain blocked even when prose `changes` is present.
- [x] 4.4 Add source-contract coverage for improved routing markers and user-safe error surfacing paths.

## 5. Verification

- [x] 5.1 Run `python3 -m py_compile` on touched runtime and test files.
- [x] 5.2 Run targeted regression suites covering structured ops, mechanical followthrough, and the new recovery tests.
- [x] 5.3 Run `openspec validate tt-character-ops-runtime-recovery-and-target-normalization` and resolve any artifact issues before implementation handoff.
