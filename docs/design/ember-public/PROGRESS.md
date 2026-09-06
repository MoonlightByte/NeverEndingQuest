# Public Ember implementation ledger

## Startup, ledger and safe authoring pass — 2026-09-05

Six startup/bootstrap browser checks and nine Journal/Storage cases now pass.
Personal visual inspection found legacy full-height black/Courier character
loading, small sheet notices/errors and small recovery status text. Desktop
presentation now follows Ember while explicit phone checks preserve original
styles. Storage read failures now report failure instead of claiming empty data.
Independent source/visual reviews and same-page retry checks are clean within
this scope. All 291 unit tests pass with the current frontend source in the
isolated Linux export; build/lint succeed (16 warnings), and ten main visual/
interactive regressions pass without updating goldens.

An actual-handler authoring probe verified synthetic pack creation, duplicate
rejection, ZIP export/preview/import, byte-identical portrait round trip and
recoverable deletion. Builder incomplete-input/idle-cancel/list checks start no
jobs. Independent review confirmed this bounded evidence. The pre-existing
placeholder merge endpoint remains nonfunctional, explicitly not accepted.
See WORKFLOW-REVIEW.md for commands, captures, exact limits and retained evidence.
No public-main publication, real campaign mutation or paid inference occurred.

## Lifecycle, edge-state and intermediate-width pass — 2026-09-05

Actual public save/list/restore/delete/reset handlers and filesystem operations
now pass in disposable campaigns for both essential and full save modes. No live
engine or developer credentials are involved; process exit/restart sleep are
intercepted and backups retained. See LIFECYCLE-REVIEW.md for the exact source
commit, reproduction, assertions and remaining live-browser/restart limits.

Four new browser cases pass: full save mode and selected Load (including hover
and phone fallback), deliberate reset/cancel, blocking module failure versus
nonblocking compression failure, and a twenty-combatant processing state.
Primary-agent screenshots exposed legacy inner Load colors/type and a generic
hover override; both were fixed and independently re-reviewed. The combat round
badge also now uses brass/muted/text Ember colors and readable desktop type,
without altering its phone styles, round value or mechanics. Its 27 existing
party unit tests pass with the changed component overlaid in the isolated export.
Production build and lint pass (16 existing warnings); ten main visual/interactive
regressions passed without updating goldens after the final Load/combat correction.

The plan-required intermediate-width drawer study is delivered separately at
http://localhost:4214/intermediate. Three Chromium tests pass at 1024/1180 and
touch; the independent architecture review is clean. Primary agent personally
inspected 1024 main/sheet and 1180 initiative against the locked language; the
author inspected all ten captures. This is an unapproved review-only prototype,
not a production breakpoint/navigation change. The implemented React game remains
available at http://localhost:4204/play/ with scripted data. Final owner approval
and the remaining acceptance-matrix work are still open; no public-main merge.

## Additional acceptance fixes — 2026-09-05

The post-handoff audit made further concrete progress rather than treating owner
inspection readiness as release completion. Provider persistence failure now
leaves live settings unchanged (`c957f93`); simultaneous selections preserve
write/apply/broadcast order. Real handlers/SDK/local-stub suite: 25 pass. Browser
provider suite: six pass, plus desktop contrast/phone fallback check. Reopening
an idle Settings panel no longer displays old endpoint-test results.

Actual missing-build/legacy/coexisting React and both Flask static entry points
passed a disposable probe. The probe exposed a shared-token-only build freshness
gap; the launcher now watches that exact imported file. Nine launcher tests pass.
Final unit rerun: 31 files / 291 tests; build/lint pass (16 lint warnings remain).
Ten main visual/interactive preview checks pass with no golden changes. Primary
agent personally inspected provider PASS/FAIL captures after contrast correction.
See HANDOFF.md and ACCEPTANCE-MATRIX.md for exact scope and unverified gates.

## Owner inspection checkpoint — 2026-09-05

Full implementation checkpoint `e6f83c5` is saved on the inspection branch.
See [HANDOFF.md](HANDOFF.md) for the running interactive preview, exact final
receipts, intentional visual differences and outstanding release/owner gates.
Clean installation/build and 31 files / 287 unit tests pass after correcting a
startup test to account for existing in-flight request coalescing. Current-main
isolated Flask browser recheck: 13 pass. Fresh independent feature and bounded
architecture reviews closed their reported findings. Additional map/operation
screenshots were personally inspected. These results supersede the pending
rechecks in the historical integration checkpoint below; they do not certify
100% parity, live provider inference or owner acceptance.

## Full-screen integration checkpoint — 2026-09-05

The implementation is now on `feat/ember-public-complete`, with public main
through `21702a7` merged in `844d6b8`. Public main has not been modified or pushed.
The previous entries below are historical snapshots, not the current scope limit.

Implemented desktop surfaces now include character/ability/feature inspections,
inventory/search/storage, player and NPC spell/scroll details, all seven NPC
detail actions and original media, maps/debug, sectioned settings and startup
recovery, save/load/reset/journal/update/operation chrome, and all six toolkit tabs
plus standalone builder. Shared modal/audio ownership, active-pack artwork
freshness, inventory view continuity and dice continuity received independent
feature and architecture review and corrective browser tests.

The actual React preview at `http://localhost:4204/play/` now includes populated
NPCs, inventory, scroll aliases, journal/storage and scripted turns. `/toolkit`
and `/builder` expose the actual themed templates with sample listings. This is
explicitly not a live AI campaign: provider/save fixtures are simulated, and
toolkit mutations or paid generation are rejected with a preview explanation.
Never enter real credentials into these fixtures.

Verified receipts from this integration checkpoint:

- TypeScript/Vite build passed. Full Vitest run: 29 files / 281 tests passed;
  additional reference-timeout/view-state/dice focused run: 26 tests passed.
- Actual isolated Flask route/hydration/NPC/media/inspection/reconnect suite:
  11 Playwright tests passed. Original artwork was retained in the media test.
- Public shell and responsive boundaries (360, 390, landscape, 760, 761, 1023,
  1024): 13 tests passed, including rolls/draft/tab continuity across resizing.
- Expanded interactive preview: four tests passed for all NPC actions,
  inventory view state, alias scroll metadata, journal/storage, long feature
  scrolling, and unchanged-versus-changed media revision handling.
- Provider UI fixtures: three tests passed; real Python provider-handler
  contract suite: 11 passed. These do not prove paid inference.
- Toolkit/builder: six browser tests passed at 1586 and 390, including real
  open/cancel handlers, nested focus, truthful failure/download notices and
  populated-table/toast containment. Network was intercepted; no jobs executed.
- Actual standalone Flask `/` and 14 CSS/font assets returned successfully in
  a disposable export. The probe exposed the existing missing `Flask-Cors`
  dependency; it is now declared in public requirements. No job was started.
- Reviewed main-screen goldens refreshed at 1586, 1920, 1440 and 1366; six visual
  checks passed including optional-image and short-screen scrolling behavior.
  Changed baseline pixels represent the distinct dice glyphs and explicit
  keyboard-accessible party Details links, not an unreviewed tolerance increase.

Primary-agent visual review included the locked reference, current 1586 main
render/diff, 1366/1920 layouts, populated NPC sheet, settings/provider/voice and
save surfaces. Additional map/operation captures and final integration review
are still being completed. No 100% pixel-parity claim is made: original images,
public controls, explicit accessibility affordances, browser font rendering and
authored vector icons differ intentionally from the raster concept.

Remaining before final handoff: finish the latest cross-screen visual pass and
fresh independent feature audit, rerun against a fresh committed current-main
runtime export, save the final review artifacts, and obtain owner review. All
unproven acceptance rows remain open; no merge into public main is authorized.

## Inventory/spell inspection implementation — 2026-09-05

First post-audit implementation batch adds desktop Ember inventory/spell panels
and shared nonmodal detail cards with hover/focus preview, click/tap pinning,
visible close, Escape and scrollable viewport-clamped placement beside the sheet.
Inventory and magic-item details expose supplied equipment facts; inventory now
uses the same coin component as the main character sheet. Existing phone UI and
public game action contracts are preserved.

Player spell reference lookup now follows the actual public compatibility-map
normalization, including Unicode aliases. Reference content includes range,
duration, components/materials, ritual, concentration, higher-level text and
attribution. A test compares all shipped names/aliases with the actual Python
reference index. Python is a test dependency only, configurable with
`NEQ_TEST_PYTHON`; it is not added to the browser bundle.

Independent feature/architecture reviews exposed and prompted fixes for pure
hover Escape, passive-hover stealing pinned focus, metadata row layout, missing
item subtype/level and inherited orange spell-summary text. Personal screenshot
inspection also moved popups beside the rail so they do not cover adjacent items.
These are code fixes, not just plan updates.

Still pending: inventory state continuity F1; NPC and scroll spell-reference
integration; full modal/portal stack A4; responsive owner continuity; media/audio
lifecycle; remaining screens and final visual parity. This batch must not be
reported as closing F5 across all consumers or the complete Ember redesign.

Verification: five real-Flask inspection browser tests pass, including touch,
hover-only Escape, pinned focus, switching/closing and viewport bounds; two
real-runtime smoke tests pass. All 28 focused sheet/reference tests pass, build
succeeds, lint has only the 11 inherited warnings, and all six main visual checks
pass without changing existing goldens. Both independent reviewers re-reviewed
the fixes and personally inspected final captures, reporting no remaining
must-fix findings in this bounded batch. Main agent personally inspected them too.

Review captures: [inventory](captures/inventory-inspection.png),
[spells at 1024px](captures/spell-inspection.png). Synthetic public runtime data
intentionally lacks matching portraits; these captures prove neither artwork
parity nor full-screen completion. The canonical spell name is retained inside
the detail body (sometimes repeating the trigger name) for alias identification.

## Repeated independent review — 2026-09-05

At the owner's request, separate feature-development and architecture agents
reviewed the plan against public/Ember code and each personally viewed the locked
design image. Three rounds produced ten findings, all incorporated as explicit
requirements in `TRANSITION-GATES.md`. Architecture returned planning-clean in
round 2; features returned planning-clean in round 3. See `REVIEW-LOOP.md` for
scope, closure and the mandatory repeated code-review process during implementation.
This closes planning omissions only, not the known implementation or visual gaps.

## Owner review and independent audit — 2026-09-05

General approval of the additional-screen direction is now received, conditional
on completeness of information/interactions and correction of visual gaps. Earlier
pending-approval entries below are historical, not the current blocker.
An independent agent reviewed both codebases and the plan; findings and required
gates are recorded in `INTERACTION-PARITY-AUDIT.md`, now linked from the plan.
The audit rejects resting-screen goldens as proof of tooltip/media/NPC parity.
The full redesign remains incomplete; no final visual or public-main approval
has been given. Next implementation follows the audit's priority order.

## Current checkpoint — 2026-09-05

Implementation branch: `feat/ember-public-complete`.
Public main was fetched and verified at
`5fe14683f2c2edfae447249c44e10b501b8c074c` before branching. The branch also contains
the plan-only commit `c7e890e`. No private history has been merged or cherry-picked.
No public push, main merge or deployment has occurred.

This checkpoint is baseline evidence and **draft design review**, not the finished
port. Product source and backend behavior are unchanged. The complete objective
and all release gates in `PORT-PLAN.md` remain in force.

## Baseline evidence

Executed in the unmodified public frontend before product changes:

- `npm ci`: succeeds; existing audit reports three vulnerabilities (one moderate,
  two high). Dependency remediation is not silently included in the UI port.
- `npm run build`: succeeds; 118 transformed modules, CSS 83.13 kB and JS
  436.61 kB (uncompressed build report), before adding self-hosted fonts.
- `npm run lint`: succeeds with 11 existing warnings.
- `npx vitest run`: 19 files / 244 tests pass; `src/services/socket.test.ts`
  cannot initialize because `services/socket.ts` accesses `document` in its Node
  test environment. This is observed on the untouched baseline, not a UI regression.
- Public fixture browser checks: all 7 tests in `player-shell.spec.ts` and
  `map-tab.spec.ts` pass, covering basic shell/dialogs, route placeholders, phone
  overflow, first turn/combat, save round-trip and map controls.

These fixture tests do not prove the real legacy page, real provider calls,
restart persistence or a live campaign. Do not count the mock server's placeholder
legacy HTML as a runtime legacy audit. That baseline work remains outstanding.

## Review gallery

From `web/frontend`:

```sh
node e2e/ember-review-server.mjs
```

Open `http://127.0.0.1:4202`. The Screen selector exposes 25 draft specimens.
Direct examples: `/?screen=settings`, `/?screen=inventory`, `/?screen=packs`.
`&capture=1` hides only the review toolbar for fixed-viewport screenshots.

The server is loopback-only, read-only and uses an explicit file allowlist. It
has no Socket.IO, game APIs, provider calls or writable operations. Inputs and
non-navigation buttons are specimens only. Never enter real credentials here.
Existing public artwork is referenced in place; no image has been regenerated.
Character assignments are illustrative, not new canonical campaign data.

The prototype temporarily uses the same Google Fonts stylesheet as the current
public player. Production implementation must self-host licensed font files before
visual baselines are locked; network font fallback cannot count as verified parity.

Reproduce the draft screen checks:

```sh
NEQ_EMBER_REVIEW=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4202 \
  npx playwright test e2e/ember-review.spec.ts --workers=1 --output=test-results/ember-review
```

The opt-in tests capture all 25 screens at 1586×992, require successfully decoded
artwork and no desktop page overflow, and check basic review navigation and a
390px settings layout. They are **not** game functional tests, approval evidence,
full accessibility tests, or parity checks against the locked main reference.

Personal visual pass: inspected settings, inventory and graphic-pack screenshots.
Found settings footer below the visible scroll area; changed the dialog specimen
to keep header/footer fixed with independently scrolling contents. Additional
screen states, detailed toolkit forms and all responsive variants still need review.

## Coverage / acceptance status

| Scope | Current evidence | Still required |
| --- | --- | --- |
| Main story / character / combat | Static family specimens; original main design already approved | Port public React owners; inline images; reference comparison; functional tests |
| Inventory / spells / NPCs / maps / debug | Draft main-panel specimens | Detailed popups, empty/error states, actual components and handlers |
| Settings / voice | Draft sectioned modal; source handler trace | Owner design approval; provider matrix and real-handler persistence tests |
| Journal / storage / save / load / reset | Draft modal treatments | Exact public data/confirmation text, child dialogs, actual state transitions |
| Startup / progress / update / exit / media | Draft family treatments | Runtime state inventory, existing workflows and full edge-state captures |
| Six toolkit tabs / builder | Draft visual treatments using existing public assets | Full parameter/nested-dialog audit, safe runtime exercises, implementation |
| Phone / intermediate widths | Draft settings overflow check only | Existing behavior baseline, user-approved responsive decisions, complete checks |
| Public release | Separate public branch only | Complete implementation, full review, explicit owner approval before main |

No additional-screen specimen is considered approved until the owner explicitly
approves it. The review gallery is not a substitute for the actual product or a
redefinition of the full goal. Final visual/functional review is still mandatory.

## Source findings to verify next

- Provider select emits `set_model_provider`; Python calls
  `model_config.set_provider` then `persist_provider`, and emits `provider_changed`.
  Runtime persistence-failure behavior must be tested before any diagnosis/fix.
- Local endpoint save keeps the stored key for a blank field. The endpoint probe
  tests posted values and uses `not-needed` when the posted key is blank. This
  distinction needs explicit UI copy/tests, not assumptions about saved credentials.
- OpenAI/Gemini key setters document cached-client/restart limitations. Validate
  before promising immediate hot-switching of every existing provider client.
- React declares `recover_startup_handoff` in its contract, but a source search
  found no React emitter. `StartingPanel` tells failed-start users to recover from
  settings. Verify the real failure/recovery path before claiming a user-facing
  defect or proposing a new recovery control.
- Standalone builder is served by `module_builder_web.py` at `/`; the toolkit
  also embeds a builder view. Test both rather than invent a route in the game app.

## Next execution steps

1. Complete isolated real-runtime baseline and provider tests without production
   credentials or campaign writes; record failures with reproductions.
2. Port the already-approved main Ember composition to public-owned React code,
   including licensed font assets and theme inheritance for portals.
3. Incorporate owner feedback on the additional-screen gallery, then implement
   every row in the full plan, adding detailed state references where still missing.
4. Repeat personal screenshot corrections and functional regression gates, with
   final owner review before any public main integration.

## Main React port checkpoint — 2026-09-05

The approved main composition is now implemented as an initial public React
pass. This is not full-plan completion or visual sign-off. Only audited
presentation hunks were transferred: scoped CSS/context/icons, character stacking,
optional inline message images, dice/composer placement and vertical party rails.
AppShell, input, TTS, image tools and tab ownership were adapted to their public
implementations rather than replaced by private versions. The latest public
no-character notice remains intact. Public providers, startup, save/load/reset,
toolkit, update and exit are not replaced with hosted account/campaign controls.

Cinzel and Crimson Text are now self-hosted with their license and provenance;
the product no longer loads a font CDN. Production artwork and model prompts
are unchanged. Initial desktop activation is 1024px and above; below that the
existing public shell remains active. Intermediate-width and full mobile review
are still required, not exempted by that temporary boundary.

Personally inspected the first actual public browser render at 1586×992 and a
combat/map state. Column composition, sheet stacking and composer placement are
present. Moved the existing time-of-day thumbnail into the rail heading and made
the heading reflect combat. The default fixture does not serve character/logo
artwork, so those captures have missing images and cannot prove artwork loading
or reference parity. A media-capable public fixture and populated reference state
remain necessary. Other tabs/dialogs retain their original rendering pending the
additional-screen design review and subsequent implementation.

New tests check five desktop widths, public action reachability, keyboard tabs,
combat ownership and the phone boundary. Message unit tests check optional image
placement, no reserved image space, original action inputs, non-Ember behavior
and safe text rendering. Viewport tests cover change subscription and cleanup.
The initial browser pass exposed a test selector counting a decorative fallback
initial as name text; the assertion now checks the actual accessible name and
the initial is explicitly decorative. This was not an initiative gameplay defect.

Checkpoint verification: production build succeeds; all 14 selected browser tests
pass (7 new Ember tests plus the 7 existing public shell/map checks); 65 existing
focused unit tests, 4 new message-presentation tests and 2 viewport tests pass.
Lint succeeds with inherited warnings; diff whitespace check is clean. A final
fetch still reports zero public-main commits missing from this branch. These
scoped checks do not replace the remaining full-plan/runtime/visual gates.

## Provider contract verification checkpoint — 2026-09-05

Added a write-capable settings fixture and three browser tests covering all four
provider selections across browser reload, endpoint/model save, blank-key presence,
posted endpoint success/failure and a rejected selection followed by retry. All
three pass against the actual built public React client on an isolated fixture
process. The fixture stores presence flags only, not typed secrets; its test-only
reset/failure controls are not production routes. It models protocol responses,
not real provider inference or durable backend storage.

Separately, `web/frontend/e2e/provider_contract_test.py` runs eleven passing Python
tests using the actual production handler bodies and a fresh temporary copy of
`model_config.py`. Real file persistence and fresh module reload are exercised;
OS credentials and provider network calls are replaced with isolated test doubles.
No developer settings, actual keys or production campaign is accessed. Handler
source is compiled without importing full application startup. One test retains
the production event decorators and routes selections/getters through a minimal
real Flask-SocketIO app, including reconnect and settings-module reload. These
checks do not prove full game-server boot, a process restart or real model responses.

Coverage: four providers persisted/reloaded, invalid provider rejection, endpoint
updates preserving a blank key without echoing it, OpenAI/Gemini key status-only
responses, posted-value probe behavior, model mismatch warning and empty URL.
No gameplay or production provider handler was changed in this checkpoint.

Reproduce (from repository root):

```sh
python -m pytest -q web/frontend/e2e/provider_contract_test.py
```

Browser checks (from `web/frontend`, using a separate terminal for the server):

```sh
NEQ_E2E_PORT=4203 node e2e/mock-server.mjs
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4203 npx playwright test e2e/ember-providers.spec.ts --workers=1
```

Remaining provider gates include the real Flask/Socket.IO integration with
temporary profiles, full backend restart, all failure/disconnect states, optional
real-provider turns with approved credentials and the eventual settings redesign.
The 14 existing Ember/public browser checks also pass with the expanded fixture.

## Populated visual checkpoint — 2026-09-05

Added an opt-in media-capable public fixture, preserving existing public artwork
and isolating synthetic character assignments from production. Personally reviewed
four populated desktop captures and saved browser regression goldens. See
`VISUAL-REVIEW.md` for reproduction and the open reference-differences register.
This is not exact concept parity or additional-screen approval. The populated
fixture replaces the earlier missing-artwork captures for main-screen review.

Public main was fetched again at `5fe14683f2c2edfae447249c44e10b501b8c074c`;
`git rev-list --count HEAD..FETCH_HEAD` reports zero missing upstream commits.
No public main integration or push has occurred.

## Responsive boundary repair — 2026-09-05

New browser checks exercise typed turns at 360×800, 390×844, 844×390,
760×800, 761×800, 1023×768 and 1024×768, plus resizing across the Ember
breakpoint while preserving an unsent draft and selected inventory panel.
The first run exposed page overflow at 761px: the inherited desktop CSS forced
an unbroken header-action row. Source inspection confirmed that rule exists in
the public-main baseline. The last sheet tabs were also clipped.

Scoped compatibility CSS at 761–1023px permits header wrapping and horizontal
scrolling of the sheet tabs and game-panel header. Existing phone rules and the
approved Ember desktop composition are unaffected. Personally inspected the
repaired 761px render with the Map tab keyboard-focused. The tablet still uses
the existing public layout, not a newly approved Ember tablet design. These
checks do not substitute for the outstanding full mobile, zoom, touch, assistive
technology and all-screen accessibility gates.

Verification: all eight responsive tests pass, including keyboard access to Map,
D4 roll and Clear at intermediate widths. The seven existing Ember shell checks
pass; all six populated visual checks pass without changing their goldens after
the header/tab repair. Build and lint succeed (11 inherited lint warnings).
Also personally inspected the final 761px dice-focused capture: the quick-roll
row scrolls to D4 within the panel instead of clipping the focused control.

## Isolated real-server integration — 2026-09-05

Added `web/frontend/e2e/ember_runtime_server.py`: it exports committed public
files to a fresh temporary directory, copies the locally built frontend, installs
the example configuration, disables OS credential access before game imports,
and rejects external Python socket connections/DNS. It runs the existing
`tests/react_parity_server.py` against a separate synthetic campaign. No developer
configuration, ignored saves or settings are copied. The printed temporary
directory is retained for inspection. This is a test runner, not a hardened
security sandbox; do not expose it publicly or use it with real credentials.

The full Flask app successfully boots in this export. New opt-in browser checks
exercise public React hydration, inventory, save-list display, settings reachability,
combat and transport reconnect through real production routes/handlers. The
underlying parity harness still replaces provider persistence, start, image,
endpoint probe, update and save listing with deterministic doubles. This does not
prove actual model turns, durable provider settings, actual restore/restart or
toolkit writes. Those original full-plan gates remain open.

The integration exposed a pre-existing Load-dialog keyboard problem: its legacy
shell had neither a primary input nor an initial focus target, so Escape stayed
on the underlying page. The shared shell now focuses a body action (or its card
as fallback). Save's explicit input focus remains unchanged. Added regression
coverage for initial focus, Escape close and focus return to the Load trigger.
No visual layout or game/provider contract changed in this repair.

Reproduce from repository root (first build `web/frontend`):

```sh
python web/frontend/e2e/ember_runtime_server.py --port 4205
```

In another terminal, from `web/frontend`:

```sh
NEQ_E2E_REAL_RUNTIME=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4205 npx playwright test e2e/ember-runtime.spec.ts --workers=1
```

Both integration tests pass. The first also opens the actual legacy `/` page and
waits for its character and transcript hydration before opening React `/play/`;
this is stronger fallback evidence than the old Node fixture's placeholder HTML.
It is still only a scoped smoke check, not a full legacy workflow audit.
All 25 focused dialog/operation unit tests pass; build and lint succeed with
the 11 inherited warnings. Personally inspected the real-runtime Load capture;
its existing dialog treatment is retained pending the additional-screen design
review, with initial focus now inside the dialog.
