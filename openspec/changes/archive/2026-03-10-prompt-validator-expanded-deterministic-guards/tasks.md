## 1. Contract and Tests

- [x] 1.1 Add focused contract tests for the expanded deterministic guard domains.
- [x] 1.2 Add tests that lock cantrip/no-slot legality and explicit slot-underflow guard expectations.
- [x] 1.3 Add tests that lock explicit unconscious-vs-HP contradiction expectations.
- [x] 1.4 Add tests that lock explicit ammo legality expectations beyond simple remove phrasing.
- [x] 1.5 Add tests that lock explicit short-rest and long-rest duration minimums.

## 2. Helper Expansion

- [x] 2.1 Extend deterministic precheck helper coverage for explicit spell-slot legality contradictions.
- [x] 2.2 Extend helper coverage for explicit unconscious-vs-HP contradictions.
- [x] 2.3 Extend helper coverage for explicit ammo-spend legality checks.
- [x] 2.4 Extend helper coverage for parseable rest-duration legality checks.

## 3. Pipeline Wiring and Narrow Contract Parity

- [x] 3.1 Wire the expanded helper checks through the existing deterministic precheck path.
- [x] 3.2 Add or update narrow source-contract tests for the validation pipeline callsite.
- [x] 3.3 Update compressed prompt/validator wording only if implementation reveals contract drift for the new guard domains.

## 4. Negative-Path and Fail-Open Verification

- [x] 4.1 Add ambiguous-text tests that confirm fail-open behavior remains intact.
- [x] 4.2 Add deterministic negative tests for each new contradiction class.
- [x] 4.3 Verify no scope creep into combat-flow or broad NLP interpretation.

## 5. Verification

- [x] 5.1 Run targeted deterministic guard contract tests.
- [x] 5.2 Run syntax checks for all touched Python files.
- [x] 5.3 Run `openspec validate prompt-validator-expanded-deterministic-guards`.
