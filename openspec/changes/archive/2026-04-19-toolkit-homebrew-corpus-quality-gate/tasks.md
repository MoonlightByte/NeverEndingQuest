## 1. Corpus Fixture Contract

- [x] 1.1 Define the canonical Phase 8 fixture list for public uploader acceptance using tracked in-repo markdown fixtures only.
- [x] 1.2 Add a small shared helper for corpus fixture discovery/reporting so tests and smoke scripts use the same fixture metadata.
- [x] 1.3 Keep the corpus gate additive and toolkit-only; do not change gameplay runtime.
- [x] 1.4 Do not hardcode developer-local paths; if extended external corpus support is added, require explicit operator-supplied input.

## 2. Normalization And Review Contract Coverage

- [x] 2.1 Add normalization snapshot/contract tests that verify representative tracked fixtures produce a bounded normalized packet and review summary shape.
- [x] 2.2 Ensure readable fixtures no longer fail the uploader at preflight solely because of structural ambiguity.
- [x] 2.3 If optional external corpus mode exists, report skipped external fixtures explicitly with reason when the operator-supplied path is unavailable.

## 3. End-To-End Upload Outcome Coverage

- [x] 3.1 Add fixture-driven uploader regression coverage for at least one clean success path and one bounded blocked/failure path.
- [x] 3.2 Assert that terminal uploader outcomes classify into the allowed bounded set: `completed`, `not_publishable`, `finishing_failed`, or `quarantined`.
- [x] 3.3 Fail the corpus gate on any unclassified hard error or silent success/failure mismatch.

## 4. Developer/Public Upload Parity Checks

- [x] 4.1 Add parity-oriented checks comparing developer ingest outcome mapping (`ready_status`, `publishable_status`) to uploader terminal states for representative fixtures.
- [x] 4.2 Verify that publishable fixtures map to uploader `completed`, while blocked publishability maps to `not_publishable`.
- [x] 4.3 Keep parity checks contract-level only; exact byte-for-byte report parity is not required.

## 5. Manual Smoke And Reporting

- [x] 5.1 Add a golden-path smoke script that runs the tracked corpus gate and emits a concise operator-facing summary.
- [x] 5.2 Emit bounded reporting for attempted fixtures, skipped fixtures, terminal classification, parity result, and overall gate result.
- [x] 5.3 If optional external corpus mode exists, make the smoke script safe when the operator-supplied path is absent.

## 6. Verification

- [x] 6.1 Run targeted syntax checks for any new Python files added in this slice.
- [x] 6.2 Run the new corpus/fixture/parity test suites.
- [x] 6.3 Re-run existing toolkit homebrew uploader regression suites to confirm no regressions.
- [x] 6.4 Run `openspec validate toolkit-homebrew-corpus-quality-gate`.
