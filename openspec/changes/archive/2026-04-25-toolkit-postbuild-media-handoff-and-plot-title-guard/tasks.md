# Tasks: toolkit-postbuild-media-handoff-and-plot-title-guard

## 1. OpenSpec Contract
- [x] 1.1 Define the readiness boundary for toolkit manual-only monster media debt.
- [x] 1.2 Define the semantic boundary for plot titles with authoritative location binding.
- [x] 1.3 Define reporting expectations so manual handoff debt remains visible after readiness relaxation.

## 2. Toolkit Readiness Fix
- [x] 2.1 Implement a deterministic toolkit-only readiness override for gameplay failures caused solely by structural manual-only monster media debt.
- [x] 2.2 Preserve toolkit media policy payloads, remediation guidance, and explicit reason metadata.
- [x] 2.3 Ensure mixed gameplay blockers still fail readiness.

## 3. Plot-Title Semantic Fix
- [x] 3.1 Implement authoritative-binding detection for plot points using `location` or `involvedLocations`.
- [x] 3.2 Prevent authoritative-bound plot titles from being treated as destination-eligible evidence.
- [x] 3.3 Preserve existing title extraction behavior when authoritative binding is absent.

## 4. Regression Coverage
- [x] 4.1 Add a readiness regression where toolkit-source media-only gameplay debt no longer fails readiness.
- [x] 4.2 Add a readiness regression proving non-media gameplay blockers still fail.
- [x] 4.3 Add a semantic regression covering the `PP006`-style authoritative plot-title case.

## 5. Verification
- [x] 5.1 Run targeted readiness and semantic regression suites.
- [x] 5.2 Run publishability/reporting validation relevant to the changed contracts.
- [x] 5.3 Capture a canary result for `Murder_at_the_Drowning_Lass` showing readiness no longer fails on media-only toolkit debt while semantic blockers reflect only true unresolved issues.
