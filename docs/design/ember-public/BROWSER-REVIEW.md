# Ember browser and final interaction review

This receipt supplements, not replaces, the screen inventory in
[ACCEPTANCE-MATRIX.md](ACCEPTANCE-MATRIX.md). The owner preview is the actual
public React implementation with scripted data, not a live provider session.
No owner campaign, provider credentials, reset or updater was used in this pass.

## Browser coverage and limits

Firefox 151.0 (Playwright firefox-1532) passed 69 distinct cases before the final
operation/empty-state fixes: 41 preview/confirmation/responsive/workbench cases,
four inspection/geometry cases, seven public-shell cases and 17 provider/map/
settings/player-shell cases. Independent review corrected an obsolete test that
tried to close Settings through its inert background opener; the test now uses
Escape and verifies focus return. Production modal behavior was not weakened.

The four new `ember-browser-compat.spec.ts` checks verify nonempty loaded Cinzel
and Crimson Text font faces, decoded original sample images and all six roster
background images, reference-column geometry, visible public header/composer/dice
controls, equipment hover/pinning ownership, complete alias-scroll metadata and
touch inspection. The touch check observes both Socket.IO WebSocket frames and
polling POSTs, requires observed hydration and permits only read-only events.
It does not establish absence of every possible HTTP mutation or paid operation.

Root personally compared the populated Firefox main-screen screenshot with the
locked 1586×992 reference and inspected equipment and alias-scroll details.
The column arrangement, stacked character sheet, message-owned image, brass
controls and reading typography follow Ember. Original artwork, public actions,
accessible Details controls, font rasterization and content wrapping remain
documented differences; this is not verified 100% raster equality or owner approval.

### WebKit: partial semantic evidence, no viewport acceptance

This Ubuntu 20.04 host receives Playwright's **frozen**, no-longer-updated
`webkit_ubuntu20.04_x64_special-2092` runtime (reported version 26.5). This does
not establish current Safari support. The host lacks `libGLESv2.so.2`; the Ubuntu
focal package `libgles2=1.3.2-1~ubuntu0.20.04.2` was downloaded and extracted to an
isolated test directory, not installed into the system. Its library path was
provided explicitly. Playwright's ldconfig-based host validation does not see
that isolated library, so these diagnostic runs explicitly bypassed validation
and tested actual runtime behavior instead.

Headless WPE launched but did not create a page, including a bounded attempt
with software-rendering settings. Headed GTK under Xvfb rendered a minimal page
but crashed on the game until `WEBKIT_DISABLE_COMPOSITING_MODE=1` and
`WEBKIT_SKIA_ENABLE_CPU_RENDERING=1` were both supplied. The subsequent real UI
run passed 17 semantic cases before stopping at three failures. The earlier
non-software run failed seven prerequisites, was deliberately interrupted, and
is not counted as a pass.

The software run revealed a runtime viewport mismatch, independently measured:

| Requested viewport | Actual `innerWidth × innerHeight` | Reported `screen` |
| --- | --- | --- |
| 1586×992 | 1638×1081 | 1586×992 |
| 1023×768 | 1075×857 | 1023×768 |
| 1024×768 | 1076×857 | 1024×768 |

A larger 2560×1440 Xvfb screen did not correct this offset. Thus the failed
reference geometry, short popup containment and 1023px breakpoint assertions do
not test their requested viewports. Root inspected the clipped capture. No CSS
or test tolerance was changed to accommodate this broken emulation. The 17
passes are bounded interaction evidence only; WebKit visual/responsive acceptance
and native Windows/macOS/current Safari checks remain open.

## Final code-review corrections

Independent source review plus intercepted browser reproductions found three
inherited public-main issues within the required operation-dialog scope:

- Reset disabled Cancel while preparing a restart but other dismissal paths
  could close it, leaving a late reset command. All pending dismissal paths now
  agree with the existing non-cancellable pending UI; actual unmount/disconnect
  invalidates preparation and its restart-marker write.
- Save could queue an offline command for a later reconnect. It now keeps the
  draft and save mode, disables offline submission and requires an explicit
  connected save.
- Update could start duplicate preparations and emit after cancellation. It now
  owns pending work, supports safe pre-emission cancellation and prevents stale
  marker/action writes after disconnect or unmount.

All original public payloads remain unchanged. Review reproductions intercepted
both polling and WebSocket mutation packets before the backend. Sixteen new
Reset/Update unit cases use actual restart preparation and held fetches; two
Save cases cover draft and explicit connected submission. These run alongside
the existing dialog regression suite.

Root's screenshot inspection also found a legacy gray non-caster notice.
The non-caster panel, NPC empty/error notices and scroll quantity badges now use
the existing desktop Ember status/palette system. Narrow layouts preserve their
original styles and quantity text. Three dedicated Chromium cases passed and
root inspected the updated non-caster/badge capture; independent review closed
the reported styling omissions.

## Final rebuilt application receipt

- Full unit suite: **35 files / 333 tests passed**. The existing Linux dependency
  export was reused, not freshly installed. All 147 source files matched before
  and after the run; sorted content-manifest SHA-256:
  `a8736ab1394e16536dd9d6090fda60c5c9d14bfe7b833e5a4de40e2521decb22`.
  Package and lockfile bytes also matched the worktree.
- Production build passed. JavaScript `index-B13fKR16.js` SHA-256:
  `668cc3fa4a3d90efac77173d6de28de860c452646213827aef9af5153190f52f`;
  CSS `index-CUxmWP5u.css` SHA-256:
  `920b889bde97ddfe36706ce4fc339d141ff41f52ed8772bbbed386157250b433`.
- Worktree lint exits successfully with **20 warnings**, not warning-free.
  Reset/Update add intentional operation-generation ref cleanup warnings;
  their stale-completion cases are tested rather than suppressed.
- **13 Chromium checks passed** against this build: four strengthened browser
  compatibility checks, three empty-state/badge cases and six visual/containment
  checks. All four reviewed desktop goldens passed unchanged. Root inspected
  the final main render and corrected non-caster/badge and NPC error captures.
- **48 Firefox checks passed** on the final rebuilt app: four compatibility,
  four confirmation, four interactive preview, ten responsive, three empty-state,
  six workbench, four workbench-accessibility and thirteen workbench-prompt cases.
  The 24 earlier public-shell/provider/map/settings/player-shell cases are
  separate evidence, not misrepresented as part of this final 48-case rerun.
- **Four additional operation-ownership cases passed in each of Chromium and
  Firefox**: offline Save preserves its draft and needs a new connected submit;
  pending Reset rejects every dismissal path consistently and emits once;
  disconnect invalidates Reset and requires re-entering its code; Update blocks
  duplicate preparation and suppresses a cancelled late action before explicit
  retry. The test fixture intercepts all owned Save/Reset/Update Socket.IO
  commands on polling and WebSocket transports. No real save, reset or updater
  ran. Root read the tests and personally inspected offline Save, pending Reset
  and cancelable Update captures. Independent implementation/test re-review is
  clean for the reported findings.

The owner preview's `/play/` entry was rechecked and references these exact
rebuilt JavaScript/CSS filenames. Refresh an already-open tab to load the fixes.
The branch contains the fetched public-main tip `21702a7` (zero missing commits
at the final check); none of this work is merged or pushed to public main.

## Retained local evidence

Artifact root: `/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2` (outside the repo).

- `firefox-ember-review`: original 41-case Firefox receipt.
- `firefox-browser-compat-reviewed`: four strengthened font/media/control checks
  before adding polling observation; subsequent final runs use both transports.
- `webkit-gtk-ember-review`: interrupted unsupported-renderer run.
- `webkit-gtk-software-ember-review`: 17 passes / 3 failures / 25 unrun.
- `sheet-empty-states-badges-final`: three final targeted styling captures.
- `final-desktop-review-chromium`, `final-desktop-review-firefox`: final rebuilt
  application runs: 13 and 48 passes respectively.
- `operation-ownership-chromium`, `operation-ownership-firefox`: four passes
  each against the rebuilt app, with diagnostic operation packets intercepted.

Browser binaries and the extracted GLES library are test-only artifacts in this
directory. They are not application dependencies or public distribution assets.

## Remaining owner/release gates

Review the interactive [game](http://localhost:4204/play/),
[Toolkit](http://localhost:4204/toolkit) and [Builder](http://localhost:4204/builder),
following [OWNER-TEST-GUIDE.md](OWNER-TEST-GUIDE.md). Additional-screen approval,
the separate intermediate-width proposal, opt-in live-provider journeys and
native-platform acceptance remain explicit gates. No public-main integration,
launcher-default change or claim of full live-game verification is made.
