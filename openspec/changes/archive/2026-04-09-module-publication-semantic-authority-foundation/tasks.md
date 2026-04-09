## 1. Shared Semantic-Authority Contract

- [x] 1.1 Add a shared semantic-authority helper that normalizes location aliases, destination phrases, and NPC scene-authority records from authored module files.
- [x] 1.2 Keep extraction deterministic and provenance-carrying, with explicit ambiguity and missing-authority diagnostics instead of hard-failing generation.
- [x] 1.3 Add focused helper tests for alias normalization, destination phrase ambiguity recording, and visible vs revealable NPC authority extraction.

## 2. Ingest And Toolkit-Finishing Integration

- [x] 2.1 Integrate semantic-authority enrichment into the shared ingest/publication flow so imported modules emit the new payload.
- [x] 2.2 Integrate the same helper into `web/extensions/toolkit_module_finisher.py` so toolkit-finished modules report the same contract.
- [x] 2.3 Persist additive report/state output in a shared module/report surface and make clear this improves publication preparation without claiming full `publishable` safety.

## 3. Semantic-Authority Audit Surface

- [x] 3.1 Add a dedicated audit/report script that reads the semantic-authority payload and validates uniqueness, traceability, and ambiguity classes.
- [x] 3.2 Keep the audit surface separate from `audit_module_readiness.py` for now; it should report deterministic pass/degraded/fail style output without becoming the repo gate yet.
- [x] 3.3 Add regression coverage proving weak source prose degrades safely while concrete semantic contradictions surface clearly.

## 4. Verification

- [x] 4.1 Run targeted semantic-authority tests and compile checks for touched Python files.
- [x] 4.2 Run the audit/report flow against at least one real module with known publication-semantic gaps.
- [x] 4.3 Update `plans/module-publication.md` progress notes if implementation findings change the later phase sequence.
