## 1. Tests and Contracts

- [x] 1.1 Add targeted tests for validation-routing telemetry shape and reason codes.
- [x] 1.2 Add targeted tests for touched-character truth-pack content and inventory relevance rules.
- [x] 1.3 Add source-contract tests for `main.py` telemetry/truth-pack integration points.

## 2. Routing Telemetry

- [x] 2.1 Extend validation routing helper(s) to expose deterministic telemetry fields for skip/compression decisions.
- [x] 2.2 Wire routing telemetry into the validation path in `main.py`.
- [x] 2.3 Keep telemetry additive and low-overhead.

## 3. Touched-Character Truth Pack

- [x] 3.1 Add helper to build compact mechanical truth packs for touched characters.
- [x] 3.2 Include HP/max HP, conditions, spell slots, death saves, and class feature usage.
- [x] 3.3 Include inventory only when the current touched change appears inventory-relevant.

## 4. Validation Context Integration

- [x] 4.1 Replace or reduce the current touched-character inventory-heavy validation context with the truth-pack helper output.
- [x] 4.2 Preserve fail-open fallback if truth-pack assembly fails.

## 5. Verification

- [x] 5.1 Run targeted tests for telemetry and truth-pack behavior.
- [x] 5.2 Run syntax checks and `openspec validate` for this change.
