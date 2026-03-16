## Why

Module validation currently proves only that JSON files are structurally well-formed and that selected reference types resolve. It does not prove that a module's playable movement graph and plot progression are coherent with the runtime pathing rules the narrator and travel systems actually use.

This gap allowed `Night_of_the_Restless_Dead` to pass validation while a hard UX failure remained live: room-to-room movement under Ma's inn looped back to the tavern because area `locations[*].connectivity` was missing, the CLI validator did not execute its own connectivity pass, and there was no parity check between area files, map files, and plot progression beats.

## What Changes

- Add deterministic validator checks for intra-area room reachability using the same room graph contract the runtime path graph consumes.
- Add deterministic validator checks that compare `areas/*.json` room connectivity with `map_*.json` room connection declarations.
- Add deterministic validator checks that verify plot progression locations and declared branch paths are reachable from the module start path.
- Fix the validator CLI so both human-readable and machine-readable runs execute the same full validation suite.
- Add regression coverage and sample-path smoke coverage for the new validation domains.

Non-goals:
- No narrator prompt rewrites.
- No runtime movement-system refactor.
- No forced gameplay audit for every module when deterministic graph checks can prove the contract.

## Capabilities

### New Capabilities
- `module-runtime-location-reachability-validation`: validator SHALL reject modules whose room graph is not playable under runtime intra-area connectivity rules.
- `module-map-area-parity-validation`: validator SHALL reject modules when area room connectivity and map room connectivity disagree.
- `module-plot-progression-path-validation`: validator SHALL reject modules whose plot locations or declared branch metadata are unreachable from the module start graph.

### Modified Capabilities
- `module-validator-cli-targeting`: CLI-targeted validation SHALL execute the full validation suite consistently in both human and JSON output paths.

## Impact

- Primary code:
  - `core/validation/validate_module_files.py`
  - `utils/location_path_finder.py` or a narrow reusable graph helper if needed
- New/updated tests:
  - validator contract and regression coverage in `scripts/test_*`
- Affected systems:
  - module authoring quality gate
  - startup/preflight trust in validator outcomes
  - ingest and gameplay-prep workflows

Risks and fallback:
- MUST keep checks deterministic and state-free; no LLM or gameplay simulation should be added to the validator.
- MUST fail closed only on explicit graph/progression contradictions, not on ambiguous freeform narrative text.
- SHOULD prefer reusing existing graph-loading semantics over building a second independent graph model.
- If a branch metadata contract is too loose to validate safely, the validator SHOULD warn via narrow explicit output first, then tighten only after schema/contract clarification.

Merge-safety / compatibility:
- The change is additive and validation-only.
- Single-player and tabletop runtime behavior remain unchanged; only pre-use quality gates get stricter.
