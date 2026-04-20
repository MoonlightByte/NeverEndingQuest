## 1. Same-Run Toolkit Provenance

- [X] 1.1 Update `web/extensions/toolkit_module_finisher.py` so toolkit provenance is available before toolkit-source readiness/publishability self-checks run.
- [X] 1.2 Add regression coverage for same-run toolkit provenance success and preserve watcher-source strictness.

## 2. Semantic Blocking Policy

- [X] 2.1 Update semantic audit/probe result handling so warning-only and tooling-debt degradation remain distinct from blocking semantic contradictions.
- [X] 2.2 Update publishability gate logic to fail on blocking semantic findings, not merely on warning-only degraded semantic/tooling status.
- [X] 2.3 Add regression tests for warning-only semantic degradation and fixture/tooling-debt probe outcomes.

## 3. Remediation Reporting

- [X] 3.1 Extend toolkit/CLI reporting to expose remediation categories for provenance gaps, ordering bugs, semantic warnings, tooling debt, and structured-monster media debt.
- [X] 3.2 Add tests validating remediation category reporting shape.

## 4. Baseline and Canary Workflow

- [X] 4.1 Re-run the watcher-vs-toolkit baseline matrix and persist an updated report artifact.
- [X] 4.2 Re-run `The_Hidden_City_of_Numillian` as the primary toolkit canary.
- [X] 4.3 Record which remaining Numillian failures are true content remediation versus structural/tooling debt.

## 5. Verification

- [X] 5.1 Run targeted regression suites for finisher, readiness, publishability, and semantic probe handling.
- [X] 5.2 Verify the OpenSpec change artifacts are complete and aligned with the implemented behavior.
