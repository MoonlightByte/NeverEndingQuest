## 1. Contract Locks and Test Scaffolding

- [x] 1.1 Add focused combat contract tests for the expanded deterministic contradiction classes.
- [x] 1.2 Add contract coverage for explicit HP/unconscious, ammo underflow, and spell-slot underflow guard expectations.
- [x] 1.3 Add contract coverage for forbidden phase actor, mid-enemy-batch stop, illegal exit, and illegal round-increment guard expectations.
- [x] 1.4 Add fail-open contract coverage for ambiguous or non-authoritative combat text.

## 2. Helper and Runtime Tightening

- [x] 2.1 Extend or add narrow deterministic combat guard helpers for explicit mechanics contradictions.
- [x] 2.2 Extend or add narrow deterministic combat guard helpers for explicit phase-integrity contradictions.
- [x] 2.3 Wire the new guards through the current combat validation path without widening scope.

## 3. Narrow Prompt and Validator Parity

- [x] 3.1 Inspect combat prompt and validator sources for any guard-domain contract drift.
- [x] 3.2 If needed, apply only narrow parity wording for the new explicit contradiction domains.
- [x] 3.3 Avoid widening scope into style policing, enemy ops, or roll resolution.

## 4. Verification

- [x] 4.1 Run targeted combat deterministic guard contract tests.
- [x] 4.2 Keep `scripts/test_multi_pc_combat.py` and `scripts/c5_regression_combat.py` green.
- [x] 4.3 Run `python3 -m py_compile` for any touched Python files.
- [x] 4.4 Run `openspec validate combat-expanded-deterministic-guards`.
