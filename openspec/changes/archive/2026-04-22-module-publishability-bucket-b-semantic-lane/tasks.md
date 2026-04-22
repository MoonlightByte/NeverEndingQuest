## 1. Scope Lock

- [x] 1.1 Confirm Bucket B is limited to `Keep_of_Doom`, `Night_of_the_Restless_Dead`, and `The_Hidden_City_of_Numillian`.
- [x] 1.2 Record explicit out-of-scope exclusion for `Murder_at_the_Drowning_Lass` and `The_Ancients_Lab`.

## 2. Keep of Doom Semantic Closure

- [x] 2.1 Define the semantic-authority payload closure needed for `Keep_of_Doom`.
- [x] 2.2 Define the deterministic alias closure for `breach the keep`, `hidden keep`, and `lantern inn`.

## 3. Night of the Restless Dead Semantic Closure

- [x] 3.1 Define the semantic-authority payload closure needed for `Night_of_the_Restless_Dead`.
- [x] 3.2 Define the deterministic alias closure for `cathedral main hall`, `end ritual chamber`, `main hall`, `ritual chamber`, and `ruined cathedral`.

## 4. Numillian Semantic + Provenance Closure

- [x] 4.1 Define the deterministic closure path for `paradox sanctuary`.
- [x] 4.2 Define the sidecar/provenance closure required so Numillian can move past readiness failure.

## 5. Verification

- [x] 5.1 Keep blocker classifications explicit during semantic-lane verification.
- [x] 5.2 Capture a short operator sequence for rerunning semantic audit, readiness, and publishability after each module closure lands.

Operator rerun sequence (semantic lane):
- `.venv/bin/python scripts/module_semantic_authority_audit.py --module <module_slug> --json`
- `.venv/bin/python scripts/module_semantic_probe_harness.py --module <module_slug> --json`
- `.venv/bin/python scripts/homebrew_sidecar_audit.py --slug <module_slug> --require-success --json`
- `.venv/bin/python scripts/audit_module_publishability.py --module <module_slug> --json`
