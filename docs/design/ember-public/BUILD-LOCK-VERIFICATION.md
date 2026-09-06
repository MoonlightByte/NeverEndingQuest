# Approved build: public-main synchronization — 2026-09-06

The owner-approved design remains `987f6c7`, recorded in
[OWNER-REVISION-01.md](OWNER-REVISION-01.md). Continuing build preparation fetched
public main at `3df32fa5180611a77726887fbdca381bb31fa38b`: 11 new provider/turn-loop
commits since the prior `21702a7` base. Local merge `9030ac28dea3cb2034fd9a13a44e72c856306c71`
includes them without conflicts on `feat/ember-public-complete`.

No files changed on both sides of that merge. The approved React source,
package/lockfile, static artwork/styles/fonts and templates are unchanged from
`987f6c7`. Public main has not been modified or pushed; launcher defaults remain
unchanged. This is build preparation, not a release or blanket acceptance claim.

## Verification on the synchronized source

- Production TypeScript/Vite build passes using the existing dependencies.
  Rebuilt JS `index-C0mgAqu0.js` SHA-256:
  `5b7e115fa385ed85f96ac0ee7b3314fce88addae578393c71126edd31d8a7631`.
  CSS `index-BvoZCAbG.css` SHA-256:
  `8bd548181fa9ef97662416d498900dadbb39199b2e49a68c6b502452f778b9d5`.
  The owner preview serves these assets.
- **8 Chromium owner/visual checks pass**, without golden updates: all five
  sample NPC identities, seven shared full-card menus, the book journal, compact
  desktop/phone rail behavior, four desktop goldens and optional-image/scroll
  checks. Root personally re-inspected main, full NPC card and journal captures.
- **6 disposable real-Flask Chromium checks pass**: all seven NPC detail
  surfaces, nested spell focus, keyboard full-card access, live socket-listener
  inventory/features/slots updates, original portrait viewer/recovery,
  legacy/React hydration and combat reconnect. This closes the previous revision's
  explicitly deferred rerun of `ember-npc-media.spec.ts`.
- **34 Python provider-contract/launcher tests pass**, using synthetic keys,
  temporary configuration and local test doubles; no paid inference.
- Actual entry-point probe passes for the game and standalone Flask apps:
  15 shared assets per app, 3 built entry assets, 11 fonts, helper inclusion once
  per workbench entry, missing-build 503/fallback, and launcher freshness/options.
  No engine or builder job starts; outbound networking is disabled in the probe.
- The full 346-unit-test receipt and Firefox checks remain those of the approved
  revision; they were not rerun in this backend-only synchronization.

Initial attempts were not counted as passes: the preview tests skipped without
their opt-in flag; they passed after setting it. Pytest's file-descriptor capture
failed on the Windows-mounted temporary path before tests ran; a rerun with
`--capture=sys` passed. The machine's Python environment lacks the already-declared
Flask-Cors dependency. Installing Flask-Cors 6.0.5 with `--no-deps --target` into
an isolated test directory allowed the complete entry-point probe to pass;
neither global packages nor repository dependency declarations were changed.

## Retained evidence

All paths below are relative to `/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/`:

- Owner/visual captures: `build-lock-main-sync-visual-verified/`.
- Real-Flask browser captures: `build-lock-main-sync-runtime/`.
- Disposable runtime export: `neq-ember-runtime-ltxjvwuq/source`.
- Passing entry-point export: `neq-ember-entrypoints-_2bd752l/source`.
- Isolated Flask-Cors dependency: `build-lock-deps.QTGxjQ/`.

The normal owner preview remains http://localhost:4204/play/ with scripted data.
Live-provider turns, native platform/Safari checks and the other release limits
in [HANDOFF.md](HANDOFF.md) remain unverified. No actual campaign, credentials,
save/reset/update job or private-server checkout was used or changed.
