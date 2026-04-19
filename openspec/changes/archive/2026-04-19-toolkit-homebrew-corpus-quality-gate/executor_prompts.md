## Builder Prompt

Implement `toolkit-homebrew-corpus-quality-gate` from `plans/module-uploader.md` Phase 8.

Guardrails:

1. Treat this as a verification and acceptance slice, not an uploader architecture redesign.
2. Keep all changes toolkit-only; do not touch gameplay runtime behavior.
3. Reuse the existing uploader/build/finisher/publication contracts as the truth source.
4. Prefer additive tests, fixture helpers, and smoke/report scripts over route behavior changes.
5. Use tracked in-repo fixtures as the canonical acceptance corpus.
6. Fail the corpus gate on unclassified hard errors, silent outcome drift, or broken parity mapping.
7. Keep parity checks contract-level; do not require byte-for-byte report equality.
8. MUST NOT hardcode any developer-local or private path in committed files.
9. If external corpus support is added, it MUST be explicit operator input only (CLI arg, config, or env), with no default private path.

Suggested implementation order:

1. Add a shared tracked-fixture discovery/helper surface for the Phase 8 fixture list.
2. Add normalization/review contract tests for representative fixtures.
3. Add fixture-driven end-to-end uploader outcome coverage.
4. Add developer-ingest vs public-uploader parity assertions for representative fixtures.
5. Add a golden-path smoke script that emits bounded operator-facing reporting.
6. Re-run existing uploader regressions and validate the OpenSpec change.

Verification expectations:

1. Readable tracked fixture sources either reach a bounded classified terminal outcome or fail with a classified gate error.
2. At least one representative fixture proves a clean success path.
3. At least one representative fixture proves a bounded blocked/failure path.
4. Parity mapping between developer ingest and public uploader outcomes is explicit and enforced.
5. Existing toolkit homebrew uploader regressions remain green.
