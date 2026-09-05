# Public Ember implementation ledger

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
