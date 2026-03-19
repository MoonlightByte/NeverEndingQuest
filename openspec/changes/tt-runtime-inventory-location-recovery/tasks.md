## 1. Transcript and contract locks

- [x] 1.1 Add a regression test for the reliquary handoff where narration establishes `Redax -> Xorn`, but the candidate response omits the giver-side inventory update.
- [x] 1.2 Add a regression test for the later `Xorn places the relic in the explorer's pack` turn where receiver ownership is still missing and deterministic recovery must backfill it safely.
- [x] 1.3 Add a regression test for startup/history refresh where recent transcript evidence places the party in `NIG04 Priest's Lodging` while stale `party_tracker` still says `NIG01`.
- [x] 1.4 Add regression coverage proving ambiguous item transfer language does NOT mutate inventory.
- [x] 1.5 Add regression coverage proving ambiguous recent location evidence does NOT rewrite canonical location on startup.

## 2. Runtime implementation

- [x] 2.1 Add deterministic party-to-party item transfer recovery helper(s) for explicit giver/receiver/item triples.
- [x] 2.2 Add deterministic receiver-side self-stow recovery when recent transcript evidence uniquely proves current ownership.
- [x] 2.3 Wire deterministic recovery so candidate narration-only turns run inventory/location recovery before the validator skip path finalizes as `narration_only`.
- [x] 2.4 Add startup/history scene-location recovery before stale `party_tracker` location is reused for UI/history rebuild.
- [x] 2.5 Extend room-style narrated-arrival matching to use canonical room labels, stripped room titles, article-tolerant variants, and `source_room_title` metadata.
- [x] 2.6 Preserve explicit `updateCharacterInfo`, `transitionLocation`, and `updatePartyTracker.currentLocationId` precedence.
- [x] 2.7 Keep all new runtime logs ASCII-only and host-file edits marked with `# TABLETOP MODE:` comments where required.

## 3. Prompt/validator parity

- [x] 3.1 Confirm validator/source contracts do not allow one-sided explicit transfer turns to silently pass.
- [x] 3.2 Confirm narration-only skip telemetry still reports skips only after deterministic recovery opportunities have been evaluated.

## 4. Verification

- [x] 4.1 `python3 -m py_compile main.py utils/travel_state_sync_guard.py <new_or_changed_runtime_helpers> <changed_test_files>`
- [x] 4.2 Run the new reliquary transfer and receiver self-stow regression tests.
- [x] 4.3 Run the new startup Priest's Lodging recovery regression tests.
- [x] 4.4 Re-run existing narrated-arrival and validation-routing suites affected by the touched path.
- [x] 4.5 `openspec validate tt-runtime-inventory-location-recovery`

## SHOULD Notes

- SHOULD keep transfer reconciliation limited to uniquely resolvable giver/receiver/item triples.
- SHOULD keep startup location recovery bounded to recent transcript evidence rather than broad full-history searching.
- SHOULD prefer deterministic runtime recovery over any new prompt complexity.
