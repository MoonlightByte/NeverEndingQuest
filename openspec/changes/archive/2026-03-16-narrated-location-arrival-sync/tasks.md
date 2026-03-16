## 1. Transcript and packet contract locks

- [x] 1.1 Add a regression test for the Hermit's Refuge narrated-arrival transcript that SHOULD infer a party location commit.
- [x] 1.2 Add regression tests proving progress-only arrival prose does NOT commit location.
- [x] 1.3 Add regression tests proving ambiguous narrated arrival does NOT commit location.
- [x] 1.4 Add packet regression coverage for the module-level location catalog topology field.

## 2. Runtime implementation

- [x] 2.1 Extend `utils/authoritative_state_packet.py` to expose a minimal module-level location catalog in packet topology.
- [x] 2.2 Add narrated-location-arrival inference helper(s) in `utils/travel_state_sync_guard.py`.
- [x] 2.3 Wire narrated-location-arrival reconciliation into `main.py` before stale conversation-history/UI refresh can rehydrate the old location.
- [x] 2.4 Preserve explicit `transitionLocation` and explicit `updatePartyTracker.currentLocationId` precedence.
- [x] 2.5 Keep all new runtime logging ASCII-only and marked with `# TABLETOP MODE:` where host edits are required.

## 3. Verification

- [x] 3.1 `python3 -m py_compile main.py utils/travel_state_sync_guard.py utils/authoritative_state_packet.py <changed_test_files>`
- [x] 3.2 Run the new narrated-arrival regression tests.
- [x] 3.3 Run existing packet, travel, and NPC scene reconciliation regression suites affected by the touched path.
- [x] 3.4 `openspec validate narrated-location-arrival-sync`

## SHOULD Notes

- SHOULD keep the first implementation narrow enough to solve Hermit's Refuge without introducing generic scene-guessing.
- SHOULD treat alias handling conservatively unless exact canonical naming proves insufficient.
