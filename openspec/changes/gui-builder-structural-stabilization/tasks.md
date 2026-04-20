## 1. Shared Materialization Path

- [X] 1.1 Refactor `web/extensions/toolkit_module_finisher.py` to replace subprocess-based monster materialization with the shared in-process materialization helper.
- [X] 1.2 Refactor `scripts/homebrew_ingest_dev.py` to use the same shared in-process materialization helper and preserve structured result parity with the toolkit finisher.
- [X] 1.3 Keep `scripts/homebrew_materialize_monsters.py` as a thin CLI wrapper around the shared helper and verify CLI output parity remains intact.

## 2. Source-Aware Provenance and Reporting

- [X] 2.1 Add explicit source-aware provenance handling to readiness evaluation in `scripts/audit_module_readiness.py`, including fail-closed handling for unsupported sources.
- [X] 2.2 Update publishability evaluation paths in `scripts/audit_module_publishability.py` and toolkit finisher callsites so toolkit builds pass `source="toolkit"` and watcher flows preserve sidecar enforcement.
- [X] 2.3 Define and persist toolkit-native provenance expectations in `modules/<slug>/toolkit_build_report.json` or equivalent toolkit-owned artifacts so provenance failures produce source-contract diagnostics instead of generic sidecar errors.

## 3. Semantic Authority Precision

- [X] 3.1 Narrow destination phrase extraction in `utils/module_semantic_authority.py` to canonical location identity fields and explicitly bounded canonical-anchor patterns.
- [X] 3.2 Update `utils/module_semantic_authority.py` so visibly authored NPCs satisfy baseline scene authority without requiring reveal bindings.
- [X] 3.3 Update `scripts/module_semantic_probe_harness.py` so travel probes derive only from canonical destination authority and hidden-NPC failures apply only to truly hidden/reveal-only cases lacking authority.

## 4. Scene-Only Illusion Boundary

- [ ] 4.1 Audit builder/finisher/publication touchpoints to ensure scene-only illusion content remains modeled through scene-entity semantics instead of structured combatant fields.
- [ ] 4.2 Preserve strict gameplay/media blocking for entities authored in combat-valid structural fields and verify no new logic weakens those gates.

## 5. Regression Coverage

- [X] 5.1 Extend toolkit finisher/materialization tests to exercise the real in-process helper path rather than only mocked subprocess behavior.
- [X] 5.2 Add readiness and publishability tests covering toolkit-source provenance, watcher-source sidecar enforcement, and unsupported-source failure behavior.
- [X] 5.3 Add semantic authority and probe regression fixtures covering Numillian-style evocative prose, visible-only NPC authority, reveal-only NPC authority, and missing hidden-authority cases.

## 6. Verification and Re-Run

- [X] 6.1 Run targeted test suites and compile checks for finisher, readiness, publishability, materialization, and semantic authority changes.
- [X] 6.2 Re-run the improved structural pipeline against representative existing modules and record outcome changes for false-positive vs legitimate blockers.
- [X] 6.3 Re-ingest `The_Hidden_City_of_Numillian` and verify the pipeline now fails only on legitimate structured-content issues, not finisher/provenance/semantic false positives.
