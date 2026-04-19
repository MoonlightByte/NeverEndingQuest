## Why

The public Homebrew uploader now reaches the intended operational boundary:

1. upload source is preserved,
2. normalization artifacts are reviewable,
3. approved packets build through readiness,
4. finishing/publication outcomes are attached,
5. artifact persistence and retry controls are available.

What remains from `plans/module-uploader.md` is Phase 8: proving this workflow against a representative Homebrewery corpus so release confidence does not depend on single-module ad hoc checks.

That corpus must be repo-portable. The acceptance gate cannot depend on a developer-local directory or any untracked source path.

## What Changes

- Add a corpus fixture contract for representative tracked Homebrew markdown sources.
- Add normalization snapshot tests for those fixtures.
- Add end-to-end upload tests for success and bounded-failure outcomes.
- Add parity checks between developer ingest and public upload for representative fixtures.
- Add a golden-path smoke script for facilitator-style manual verification.
- Add clear pass/fail acceptance reporting for this corpus gate.
- Allow optional operator-supplied external corpus paths only through explicit CLI/config input, never through hardcoded local paths.

## Capabilities

### New Capabilities
- `toolkit-homebrew-corpus-quality-gate`: the uploader has a repeatable corpus-based acceptance suite, anchored in tracked in-repo fixtures, that validates normalization, review, build/readiness, finishing/publication outcomes, and parity expectations.

### Modified Capabilities
- `toolkit-homebrew-ingest-job-reporting`: expose a corpus gate result summary suitable for release sign-off.

## Impact

- Affected verification and test tooling:
  - `scripts/test_toolkit_homebrew_*.py`
  - tracked fixture corpus under a repo-owned fixture path
  - new corpus fixture and smoke scripts under `scripts/`
- Affected upload/build parity checks:
  - `scripts/homebrew_ingest_dev.py` (read-only parity reference usage)
  - `web/routes/toolkit_homebrew_routes.py` (no behavior redesign expected)
- Merge-safety impact: SHOULD remain additive by adding tests, fixtures, and narrow reporting only.
- SP/MP compatibility impact: no gameplay runtime change; MUST remain toolkit/import lane only.
- Privacy rule: MUST NOT hardcode developer-local directories or private corpus paths in committed code, tests, plans, or OpenSpec artifacts.
