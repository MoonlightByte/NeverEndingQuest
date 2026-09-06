# Owner revision: full NPC cards, visible party stats and parchment journal

Requested after reviewing `27c1173`. This is an intentional revision of the
right rail and journal, not an unrequested departure from the locked direction.
Existing photorealistic artwork, game mechanics and phone layout are retained.

- NPC **Details** in exploration and NPC initiative opens the same full live
  character card used by the NPC tab. It includes all seven existing conditional
  menus, supplied biography, abilities, XP/currency and portrait/media access.
  No duplicate snapshot of the NPC sheet or invented action menu was introduced.
- Right-side entries show supplied level/class, HP with a compact bar, AC, XP
  and conditions. Current roster/combat values take precedence; full player/NPC
  records supplement optional information. Unknown values are omitted, zero
  values remain visible, and enemies are not enriched from NPC/player sheets.
  Full cards match unique names, never portrait/class guesses. A missing full
  record displays an honest unavailable state instead of fabricated statistics.
- Journal restores the original parchment pages, brown ink, book binding and
  page shadows. Active and completed quests occupy separate pages; loading,
  empty and error states retain the book. Desktop uses the existing modal stack,
  focus restoration and Escape handling; phone retains its original journal.

Root personally inspected the main screen, full NPC card and parchment book.
This caught a portal-only portrait crop/legacy border and missing currency
styling, which were corrected without changing image assets. Independent review
also caught pending portrait work opening over a new full card or submenu;
existing cancellation ownership now covers both transitions. Four focused
positive/negative regressions pass, including nested-menu focus restoration.

The four main-screen visual baselines are deliberately refreshed for the
owner-requested right-rail change; the original concept reference remains
untouched. This does not claim owner acceptance of the new captures or 100%
raster parity. Root inspected all four updated desktop baselines; a subsequent
eight-case run passed without updating them again.

## Verification

- Production build and TypeScript pass: `index-C0mgAqu0.js` /
  `index-BvoZCAbG.css`. Lint passes with the existing 20 warnings.
- Full units: **38 files / 346 tests pass** using the existing Linux dependency
  export (not a fresh install). All 154 source files match before and after;
  content manifest `298a5f94711a49fccd47414be646b0368e67243e8358daffbe1ce306bd099149`.
- **22 Chromium cases pass** across owner revisions, existing preview,
  responsive and main visual checks; **16 Firefox cases pass** for the matching
  interaction/responsive subset. The owner test was then strengthened to open
  all five sample NPCs, and passes again in both engines (8 Chromium including
  the six unchanged-baseline checks, 2 Firefox).
- Journal: **12 Chromium cases pass** (3 book viewports and 9 existing
  Journal/Storage state checks), including original phone presentation.
- Independent NPC review is clean after both pending-media cancellation fixes.
  The shared full-card code retains live nested inventory updates and closes
  them on NPC removal. No save, provider, reset or authoring operation ran.

Final main/full-card/book captures are under:
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/owner-npc-journal-accepted/ember-owner-revisions-righ-d66be-nd-all-seven-original-menus/`
(`ember-party-stats.png`, `npc-full-card.png`, `parchment-journal.png`).
Firefox captures: `owner-npc-journal-all-npcs-firefox` under the same artifact root.
These are agent-reviewed captures, not owner sign-off. Prior receipts describe
earlier checkpoints; current live-provider/platform limitations remain unchanged.

Interactive preview: http://localhost:4204/play/ (refresh an existing tab).
It is the actual implemented UI with scripted data, not live AI or real saves.
No public-main merge or push is part of this revision.
