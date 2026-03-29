## 1. Contract and regression locks

- [ ] 1.1 Add transcript-driven regression coverage for the `NIG02 -> NIG03` altar-crevice descent lock case when no explicit location name or `transitionLocation` is present.
- [ ] 1.2 Add regression coverage proving same-turn descent plus combat anchors encounter state to the inferred sublocation rather than the stale parent room.
- [ ] 1.3 Add regression coverage proving ambiguous or progress-only lower-depth prose does not auto-commit location.
- [ ] 1.4 Add regression coverage proving explicit `transitionLocation` remains authoritative over any inferred sublocation commit.
- [ ] 1.5 Add regression coverage proving DM drift-question adjudication flow remains valid and unforced.

## 2. Runtime implementation

- [ ] 2.1 Add a narrow implicit-sublocation descent inference helper in `utils/travel_state_sync_guard.py` bounded to one uniquely resolvable adjacent authored target.
- [ ] 2.2 Wire inferred sublocation location commit injection into the existing reconciliation path in `main.py` before stale location truth is consumed by later processing.
- [ ] 2.3 Ensure same-turn inferred sublocation commit is processed before `createEncounter` consumes canonical location truth.
- [ ] 2.4 Keep explicit `transitionLocation` and explicit `updatePartyTracker.currentLocationId` precedence unchanged and preserve fail-open behavior for ambiguity.
- [ ] 2.5 Keep host-file logs ASCII-only and mark required host edits with `# TABLETOP MODE:` comments.

## 3. Optional authored lock-case metadata

- [ ] 3.1 If runtime determinism still needs authored assistance, add minimal additive transition-hint metadata for the Night of the Restless Dead cathedral descent lock case.
- [ ] 3.2 Keep any module metadata additive and backward compatible with existing runtime/module consumers.

## 4. Verification

- [ ] 4.1 Run `python3 -m py_compile` on changed Python files and touched regression files.
- [ ] 4.2 Run targeted travel, scene-location, and combat/location regression suites affected by the touched path.
- [ ] 4.3 Verify the cathedral descent lock case persists the corrected sublocation across restart-oriented context rebuild.
- [ ] 4.4 Run `openspec validate tt-implicit-sublocation-descent-sync`.

## SHOULD Notes

- SHOULD keep the first implementation limited to adjacent authored sublocations rather than broader module-wide scene guessing.
- SHOULD prefer additive authored transition hints over module-specific runtime hardcoding if a lock case needs extra determinism.
