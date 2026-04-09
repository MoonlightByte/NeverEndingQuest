## 1. Publishability Gate Contract

- [x] 1.1 Define the final gate contract so `ready` and `publishable` are explicit, distinct states.
- [x] 1.2 Keep publishability layered over readiness (`ready` remains useful even when `publishable` fails).
- [x] 1.3 Add focused contract coverage for status layering and exit-code behavior.

## 2. Standalone Publishability Audit

- [x] 2.1 Add a standalone publishability audit script that composes readiness, semantic publication audit, and semantic probe harness results.
- [x] 2.2 Emit explicit structured output with `ready_status`, `publishable_status`, nested gate results, blocking errors, and fix guidance.
- [x] 2.3 Make publishability success depend on the stricter release-facing decision, not just readiness.

## 3. Reporting Integration

- [x] 3.1 Expose `ready` vs `publishable` clearly in toolkit finisher reporting.
- [x] 3.2 Add any narrow bulk/reporting updates needed so the repo can distinguish structural readiness from semantic publishability without ambiguity.
- [x] 3.3 Add regression tests proving reporting surfaces preserve the distinction cleanly.

## 4. Verification

- [x] 4.1 Run targeted compile checks and publishability regression suites.
- [x] 4.2 Run the standalone publishability audit against at least one real module and capture ready vs publishable outcomes.
- [x] 4.3 Update and archive `plans/module-publication.md` once the full publication sequence is complete.
