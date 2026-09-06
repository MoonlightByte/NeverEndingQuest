# Ember public: owner inspection handoff

Branch: `feat/ember-public-complete` in `/mnt/e/NEQ-ember-public`.
Implementation checkpoint: `e6f83c5`; public main through `21702a7` is included.
Additional visual fixes: `9d930df`; review-only drawer study: `074f8cc`.
The last upstream fetch found no additional main commits. Nothing from this
public implementation has been pushed or merged into public main.

## Open and test

- Game: http://localhost:4204/play/
- Toolkit: http://localhost:4204/toolkit
- Standalone builder presentation: http://localhost:4204/builder

Separate, review-only intermediate-width drawer proposal:
http://localhost:4214/intermediate. This is not production navigation; see
[its scope and captures](intermediate/README.md) before considering integration.

These serve the implemented React app and actual themed toolkit templates, not
screenshots. They use **scripted sample state**, not a live AI campaign. No real
keys should be entered. Provider/save actions are simulated; toolkit mutations
and generation jobs deliberately return a preview explanation.

In the game, try `Look around`, then `combat` for initiative; reload to return to
exploration. Inspect the character sheet, item/spell hover and pinned details,
all seven NPC detail actions, original portrait viewers, inventory search and
storage, journal, dice, settings, and save/load dialogs. Resize to inspect the
preserved phone interface. The toolkit exposes all six tabs and builder controls;
it does not run an authoring job.

To restart this preview after building the frontend:

```sh
cd /mnt/e/NEQ-ember-public/web/frontend
npm run build
NEQ_E2E_PORT=4204 NEQ_E2E_EMBER_VISUAL=1 node e2e/mock-server.mjs
```

## Implemented scope

Character, abilities/features, inventory/search/storage, player and NPC spells
and scroll metadata, seven NPC detail actions, biography/media viewers, party and
initiative, map and debug, public provider/voice/image settings and startup
recovery, save/load/reset/journal/update/operation dialogs, six toolkit tabs,
nested toolkit confirmations, and standalone builder presentation have Ember
implementations. Inline images remain optional and message-owned. No new game
mechanics or replacement artwork were introduced.

Shared work includes accessible inspection/modal ownership, focus and Escape,
audio cancellation ownership, artwork revision invalidation, inventory view
continuity, currency and individual dice glyphs, responsive continuity, and
self-hosted fonts with licensing. See `PORT-PLAN.md` for the complete inventory
and `TRANSITION-GATES.md` for acceptance requirements.

## Verification receipts

- Clean `npm ci` and production build passed in an isolated committed export.
  Full suite with the final startup/provider-test corrections: **31 files / 291 tests pass**.
  The correction verifies coalesced startup hydration and trailing refreshes;
  it does not change production socket behavior.
- Lint exits successfully with **16 warnings**, not a warning-free claim.
- Current-commit isolated real Flask route/hydration/reconnect, inspections,
  NPC/media and supplementary surfaces: **13 browser tests pass**. A preceding
  run timed out in browser teardown after assertions; the full rerun passed.
- Interactive preview and reviewed main-screen visual goldens: **10 pass**.
  Main reference viewports: 1586×992, 1920, 1440 and 1366 widths.
- Public shell/responsive: **13 pass**, plus **2 additional viewport checks**
  at 390×460 and 793×496. These approximate keyboard space and 200%-equivalent
  CSS space, not a real OS keyboard or native browser zoom test.
- Populated map: **2 pass**. Provider UI: **6 pass**, plus **1 desktop contrast /
  phone fallback check**; real provider handler, persistence, overlapping-write,
  routing and SDK/local-stub contract tests: **25 pass**. No paid inference.
- Toolkit/builder: **6 browser tests pass**, with intercepted networks and no
  authoring jobs. Actual standalone Flask route and **14 CSS/font assets** pass
  in a disposable export; the missing Flask-Cors dependency is now declared.
- Additional actual-entry-point probe verifies missing-build 503s while legacy
  and toolkit remain usable, built React/legacy coexistence, 15 shared assets
  through each Flask app, 3 React entry assets and 11 bundled fonts. Launcher
  defaults/options are unchanged; **9 launcher tests pass**. Shared-token-only
  changes now correctly invalidate the React build.
- Final focused checks include **4 audio ownership tests** and **2 phone settings
  browser tests**, including visible keyboard focus.
- Additional lifecycle verification passes with actual handlers and files in
  disposable campaigns for both essential and full saves, restore, delete and
  reset. No real user data was touched; see [scope and limits](LIFECYCLE-REVIEW.md).
- Four extra browser edge-state checks cover full-save presentation, selected
  Load hover/phone fallback, reset confirmation/cancel, failure overlays and a
  twenty-combatant initiative list. The selected-save review caught and corrected
  inherited legacy colors/type and a higher-specificity generic hover rule.
  The combat round badge also now follows Ember's palette/type, with original
  phone styling preserved; all 27 existing party unit tests pass.
- The separate intermediate-width prototype passes three browser checks for
  keyboard/touch, focus/inertness, draft/filter/scroll continuity and sample-only
  interactions. It remains unapproved and does not change production breakpoints.
- Startup/empty-bootstrap: **6 browser checks pass**; Journal/Storage states and
  phone preservation: **9 pass**. Desktop loading/notice/error styles, recovery
  text and truthful Storage failure presentation are corrected. Full unit rerun:
  **31 files / 291 tests**; ten main visual/interactive checks still pass unchanged.
- Actual safe toolkit create/export/preview/import/delete and builder validation
  pass in a disposable export. A photorealistic portrait survives the ZIP round
  trip byte-for-byte. See [workflow evidence and limits](WORKFLOW-REVIEW.md).

Final provider fixes: `c957f93` validates and durably saves a provider choice
before applying it live, serializing simultaneous selections. The new failure
test reproduced the pre-existing public-main bug before the fix. A reopened
idle Settings panel also no longer displays cached/late endpoint-test results.
Desktop PASS/FAIL text has measured 9.79:1 / 8.35:1 contrast against the lighter
modal background stop; existing phone colors are retained.

The primary agent personally inspected the locked reference against the main
render/diff, laptop/large desktop captures, NPC details, settings and save, map,
debug/operation presentation and phone toolkit captures. Independent feature and
architecture reviewers closed their reported implementation findings after fixes
and re-review. These are bounded reviews, not blanket approval of every state.

## Differences and remaining release gates

No verified 100% raster-parity claim is made. Original public photorealistic
artwork, public-only header actions, accessible Details/inspection affordances,
authored SVG icons, actual fonts/antialiasing and content-driven wrapping differ
from the concept. No mockup-only footer or mandatory hero image was added.

Still unverified: paid/live provider turns, full real new-game-to-save/restore
journey, real generation/export/update jobs and reset process restart, every possible error or
loading state, native zoom/keyboard/safe-area behavior, Firefox/WebKit and native
Windows/macOS rendering, and formal performance profiling. Intermediate widths
retain the existing responsive ownership with containment tests; the separate
side-panel prototype is delivered for owner review, not integrated. Legacy fallback selection is
preserved and actual missing-build/route/launcher behavior has been tested.

The existing endpoint probe protocol has no request identity. If probe A times
out, probe B starts, then A replies late, the UI cannot distinguish that reply
from B. Closing/reopening an idle panel is now safe, but complete correlation
would require a separately reviewed contract change. Broader pre-existing
settings-file concurrency outside provider selection is also not solved here.

The toolkit's existing merge endpoint returns placeholder success without merging.
That workflow is not implemented by this design port and is not accepted as working.
Actual safe ZIP export/import now has backend evidence; live generation and the
full browser-to-backend authoring journey remain unverified.

See [ACCEPTANCE-MATRIX.md](ACCEPTANCE-MATRIX.md) for screen-level evidence and
remaining gaps; this checklist does not turn partial coverage into full approval.

`npm audit` reports three development dependency findings (nanoid, postcss,
undici: two high, one moderate); `npm audit --omit=dev` reports zero. Dependencies
were not automatically upgraded during the design port. These findings require
separate release triage, not a claim that the entire dependency tree is clean.

**Owner visual and functional review remains required.** This is a reviewable
implementation, not proof that every acceptance row in the plan is complete.
Do not merge or push this work into public main until the owner approves it.
