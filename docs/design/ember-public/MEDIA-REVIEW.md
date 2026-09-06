# Portrait upload and freshness review — 2026-09-05

This is a bounded F2/A2 receipt, not whole-plan acceptance or owner approval.
Original public artwork is unchanged. Upload inputs are existing public
`graphic_packs/photorealistic/npcs/ranger_marcus.jpg` and `ranger_elen.jpg`;
the existing upload handler performs its normal square crop and 256px resize.

## Actual backend defect and repair

The real `/upload-portrait` handler reported success and wrote its static PNG,
but its module copy called nonexistent `ModulePathManager.get_module_dir()`.
Using the existing `manager.module_dir` attribute repairs campaign persistence.
The single-line production correction and disposable regression runtime are
committed as `1888181`. No provider, engine, game rule or artwork was changed.

An actual-handler probe first failed on baseline `13b903e`: the static image
existed but the module image did not. After the correction, both PNG files have
the same SHA256 and 256×256 dimensions. Invalid PNG input returns failure and
leaves both copies unchanged. Retained evidence under
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/`:

- Baseline failure: `neq-ember-portrait-dcp2gwom/portrait-result.json`.
- Corrected success: `neq-ember-portrait-ae_5krm2/portrait-result.json`
  (`13b903e` plus the explicitly recorded handler-file overlay).
- Browser export: `neq-ember-portrait-kj5h7xv5/portrait-isolation.json`
  (`1888181`, no backend overlay, current working-tree frontend build).
- Final source: UI/media changes are committed as `1a0765b`; its fresh export
  is `neq-ember-portrait-ipwknqqr/portrait-isolation.json`, with no source overlay
  and a manifest of the actual copied build files.

The browser export's 16 copied build files were independently compared with
its recorded SHA256 manifest; all match. The runtime now computes that manifest
directly from the copied tree to avoid concurrent-build provenance ambiguity.

## UI behavior

Canonical upload filenames are fallback candidates without changing ordinary
legacy candidate order. An explicit successful upload takes precedence over
older aliases and animation for that player during the current session. Global
campaign/pack invalidation clears that override and restores normal video-first
resolution. Cache revisions cover exact canonical/loose/strict name aliases;
updating Ann does not shadow Ann Marie. Apostrophes, hyphens and literal percent
names have focused regression coverage.
Names ending in Thumb or Video also retain their canonical player-image stems;
suffix normalization is restricted to generated media paths and video files.

The open viewer retains the selected entity and original resolution recipe.
Its matching portrait update refreshes in place; unrelated named updates leave
it alone. Global invalidation closes it. Generation guards prevent late A media
from replacing B or reopening a dismissed viewer. Failed refreshes expose an
explicit error state and may recover after a later successful update.

## Browser verification

`e2e/ember-upload.spec.ts` passes against the actual Flask upload handler in a
fresh disposable campaign. It verifies:

1. Missing portrait and default fallback, followed by a real file-input upload.
2. New portrait in the desktop sheet and exploration rail without reload.
3. Identical static/module PNGs and the served image's matching SHA256.
4. Full-size viewer, replacement while open, successful image decoding and
   Escape/focus return. The second upload is an actual HTTP request followed by
   an explicitly injected existing named invalidation event: the normal upload
   button is correctly inert behind the modal. This is an integration check,
   not a claim that users can click through the viewer to upload.
5. Rejected PNG preserves both files and displayed portrait URLs.
6. The same uploaded portrait appears after a synthetic combat transition.
7. Phone-width upload changes the sheet URL and returns the expected bytes in
   the browser's image response; dimensions and both persisted copies are also
   checked. The final phone capture scrolls the actual sheet into view.

The primary agent personally inspected desktop, open viewer, combat and phone
captures. The main reference render was compared again with the locked concept;
layout, type, borders and controls have not changed in this media repair.
The public upload's existing 256px limit makes large viewers softer than the
concept; no replacement high-resolution art or rendering-parity claim is made.

Final committed-source run (`1a0765b`, port 4219): **one complete upload journey
passes**, with captures retained in
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/portrait-committed-review/`.
The final frontend also passes **31 files / 302 unit tests**, including all
**38 party tests**, plus **10 main visual/interaction checks** without golden
updates. Build succeeds; lint succeeds with 17 warnings. The full unit run used
the same source files copied to the existing Linux dependency export to avoid
Windows-mount worker startup timeouts; this is not a new clean-install claim.

## Reproduce safely

From the public worktree, use the game's Python dependency environment:

```sh
cd web/frontend
npm run build
cd ../..
python web/frontend/e2e/ember_portrait_runtime.py --probe-upload --temp-parent /existing/test-volume
# Start a separate fresh campaign for the browser test:
python web/frontend/e2e/ember_portrait_runtime.py --port 4218 --temp-parent /existing/test-volume
```

In another terminal:

```sh
cd web/frontend
NEQ_E2E_PORTRAIT_RUNTIME=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4218 npx playwright test e2e/ember-upload.spec.ts --workers=1
```

Every launch creates a new retained child directory. A rerun needs another fresh
runtime; never delete a real portrait to satisfy the missing-initial-art assertion.
The helper exports tracked HEAD, copies the built frontend, stubs credential
access and uses an in-process write/network/subprocess guard before application
import. It is safety containment for trusted tests, not an adversarial OS sandbox.
There is no paid generation, live game engine or access to user campaign files.

## Independent review and limits

An independent feature author and separate source reviewer closed the filename,
override and viewer findings, including defensive URL decoding. A further
independent architecture/test review confirmed actual-handler isolation and
caught a weak phone assertion; changed URL plus browser image-byte verification
now prevents a stale 256px portrait from passing. The provenance correction was
also independently re-reviewed cleanly.

This one browser journey uses a single ASCII player identity and synthetic
exploration/combat state. Alias collisions, delayed selection/cancellation,
unrelated/global revisions and video precedence rely on focused unit tests;
pack visibility/revision also has the existing browser checks. Native file-picker
keyboard/touch activation, every live reset/load interleaving, native rendering
and owner approval remain unverified. The complete F2/A2 gate is not inferred
from one upload test, and the full acceptance matrix remains authoritative.
