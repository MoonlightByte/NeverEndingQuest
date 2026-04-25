## 1. Sidebar freshness authority

- [x] 1.1 Add a persisted-report freshness authority helper in `core/generators/module_stitcher.py`.
- [x] 1.2 Make `_derive_sidebar_audit_signals(...)` fail open for failed reports that are stale, legacy, or non-authoritative.

## 2. Regression coverage

- [x] 2.1 Update `scripts/test_module_sidebar_audit_failure_signals.py` so current expected-failure fixtures include authoritative freshness metadata.
- [x] 2.2 Add coverage proving stale/legacy failed reports do not emit `brief_failure` or `media_generator_needed`.

## 3. Verification

- [x] 3.1 Run targeted compile and regression tests for sidebar failure derivation.
- [x] 3.2 Re-check live sidebar-facing behavior for `The_Hidden_City_of_Numillian` and `The_Thornwood_Watch` using current audits.

## Guidance

Keep the sidebar as a persisted-report consumer only. Do not add live audit execution to this flow.
