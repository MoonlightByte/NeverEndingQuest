## 1. Shared Finishing Pipeline

- [x] 1.1 Add a shared post-build finishing helper/service for toolkit-generated module directories.
- [x] 1.2 Reuse continuity normalization and verification logic so toolkit builds do not bypass the ingest-side quality stages.
- [x] 1.3 Add monster materialization and related post-build checks needed for combat/runtime readiness.

## 2. Toolkit Builder Integration

- [x] 2.1 Update the toolkit build thread/handler to run the finishing pass after `ModuleBuilder.build_module(...)` succeeds.
- [x] 2.2 Extend toolkit progress events so generation completion and finishing completion are reported as separate stages.
- [x] 2.3 Preserve the existing concept-builder input flow and cancellation/error behavior while the finishing stage is added.

## 3. Result Reporting

- [x] 3.1 Add structured toolkit result payloads for fully successful, degraded, and failed finishing outcomes.
- [x] 3.2 Add persistent report or sidecar output summarizing finishing-stage results for each toolkit build.
- [x] 3.3 Make clear in the UI that this parity pass improves publication readiness but does not yet satisfy the full semantic publication plan.

## 4. Verification

- [x] 4.1 Add regression coverage for finishing helper behavior and toolkit result mapping.
- [x] 4.2 Run targeted compile/syntax validation for modified builder, helper, and toolkit frontend files.
- [ ] 4.3 Smoke-test one toolkit concept build through success and one expected degraded/failure path.
