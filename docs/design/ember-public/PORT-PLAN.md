# Ember Public — complete game UI port plan

Status: general design approval received, subject to the independent interaction
and visual-completeness audit in [INTERACTION-PARITY-AUDIT.md](INTERACTION-PARITY-AUDIT.md).
Implementation is on `feat/ember-public-complete`; no public-main release authorization.
Prepared: 2026-09-05.
Repository: `MoonlightByte/NeverEndingQuest` (public).
Planning branch: `plan/ember-public-all-screens`.
Verified public main base: `5fe14683f2c2edfae447249c44e10b501b8c074c`
(`fix(ui): benign no-character notice instead of red 'Player data not found'`).
Worktree: `/mnt/e/NEQ-ember-public`.

## 1. Outcome

Bring the approved Ember Stacked visual language to the complete public game
experience, not just the active-game character screen. Cover startup, free-text
play, combat, every character/inventory/spell/NPC/map/journal surface, settings,
save/load/reset/update/recovery, media, responsive layouts, and the toolkit and
builder reachable from the game. Preserve photorealistic artwork and all existing
game rules, event contracts, local ownership, provider choices and saved data.

The approved desktop composition remains the anchor: stacked character details
on the left, chronological narration and command entry in the center, and
party/nearby people or server-ordered initiative on the right. Images remain
optional and attached inline to their messages. This is not a choice-button
adventure, a new rules engine, or a hosted-account client.

Target 100% visual parity with the approved desktop reference at 1586×992,
excluding intentional artwork differences and documented public-control changes.
Do not claim achieved parity without personal screenshot inspection. Other
screens need their own approved designs; they cannot honestly claim pixel parity
with a reference that only depicts the main screen.

## 2. What was actually inspected

This plan is based on the current public source, not the private server shell:

- `run_web.py`: `--ui react|legacy|choose`; legacy is still the default.
- `web/web_interface.py`: legacy `/`, React `/play/`, `/toolkit`, media and
  provider handlers. Preserve existing route behavior and static-asset resolution.
- `web/frontend/src/App.tsx`, `components/layout/{AppShell,HeaderBar,StartingPanel}.tsx`:
  one React shell, local start/save/load/reset/settings/toolkit/exit controls,
  first-run guidance and startup/recovery log handling.
- All current component directories under `components/{dialogs,settings,sheet,party,log}`.
- `components/settings/LocalProviderPanel.tsx`: public provider values are
  `legacy`, `openai`, `gemini`, `lmstudio`; endpoint, key and connection-test forms
  live in this file. Do not import the private split panel by assumption.
- `components/settings/SettingsMenu.tsx`: images, voice engine/voice/preview/
  autoplay, map style and provider controls.
- `theme/tokens.css`: current responsive behavior includes a 760px boundary.
  Public main does not contain the private dedicated `MobileShell` implementation.
- `web/templates/{game_interface,module_toolkit,module_builder}.html`:
  legacy game, six toolkit tabs, and standalone builder template.
- Existing colocated tests and `e2e/player-shell.spec.ts`, map and parity suites.

No live game session, real provider call or runtime screenshot audit was performed
for this planning commit. Phase 0 must verify runtime reachability and capture
baseline screens; source inventory is not proof that every workflow works today.

## 3. Branch and public/private boundary

1. Keep the private server worktree separate from this public-only checkout.
2. Before implementation, fetch public `main`, record its SHA, and update the
   implementation branch to that tip. Repeat before opening a release PR.
   Do not reset another agent's work or force-update shared branches.
3. Implement in focused public branches/commits after plan inspection. The
   planning branch changes documentation only. Never implement directly on main.
4. Do not merge or cherry-pick the private integration history into public.
   Transfer only reviewed presentation code, with public-specific adapters.
5. The design donor is the approved Ember Stacked implementation and its
   `05-ember-inline-stacked.png` reference. The reference has SHA-256
   `5ea38d43b52b6119894b0796f68087a233977e2dc79d7aaa44c6a987d2c76464`.
   During implementation, place a distribution-approved copy in this design
   directory and record its provenance. Do not copy private fixture portraits,
   account/campaign code, server documentation, credentials or runtime data.
6. Audit every added file and its history/assets before a public push. Font and
   icon licenses must accompany reusable assets. No production saves or provider
   responses containing personal information in screenshot fixtures.
7. Public main receives a reviewed PR only after the gates below. Public
   publication and changing launcher defaults are separate release decisions.

## 4. Design and implementation system

Retain the public stack already present: React, TypeScript, Vite, Zustand,
Socket.IO, Tailwind/CSS, Vitest and Playwright. No routing framework, UI kit,
state-management replacement, service migration or image-generation dependency
is needed for this port.

### Locked visual foundation

| Role | Ember value / treatment |
| --- | --- |
| Page / panel | `#080d0d` / `#0c1111` |
| Primary / secondary text | `#ddd6c8` / `#a89c88` |
| Brass / rule / frame | `#c5a06d` / `#493b27` / `#302b20` |
| Display / reading type | Cinzel / Crimson Text, self-hosted licensed files |
| Input and detail controls | Quiet dark surfaces, fine borders, visible focus |
| Primary action | Ember-red/brown treatment from the approved implementation |
| Status | Distinct text/icon plus success, warning or error color; never color alone |
| Artwork | Existing photorealistic originals and original media associations |

Use the original reference and donor CSS for the full scale, not guessed colors
from a screenshot. At the reference viewport, aim for the 62px header and roughly
29.7% / 51.3% / 19% columns. Keep compact vital/ability boxes but stacked, largely
unboxed character sections. Avoid adding decorative cards around every paragraph.
Do not propagate fixed empty footer space or desktop minimum widths to small
screens merely because they occur in the reference.

### Shared primitives and ownership

- Introduce scoped Ember tokens and a presentation root, then reusable panel,
  button, field, tabs, dialog, status, tooltip and icon treatments. Preserve
  existing components and logic wherever possible.
- Ensure portaled dialogs/tooltips inherit the theme via a dedicated themed
  portal root or explicit scope; styling only `.neq-app-grid` is insufficient.
- Keep hydration and event listeners single-owned. Moving a component must not
  duplicate polling, reconnect requests, media playback or submit handlers.
- Remove superseded inline colors incrementally where owned, rather than grow
  an unbounded `!important` override layer. Leave unrelated legacy CSS isolated.
- Public controls remain local. No Account, subscription, entitlement, hosted
  adventure library, quick-start contract or restart substitution is introduced.
- Keep present backend schemas and events. Any genuinely necessary contract
  change requires a separate proposal, schema update and consumer tests.
- Decorative motion is restrained and respects reduced-motion preferences.
  Artwork must never become a fixed hero required for an otherwise text-only turn.

## 5. Complete screen and state coverage

Each row is a required delivery item, not an optional follow-up. For every row,
capture populated, empty/loading, error and disabled states where applicable.

| Surface and current owner | Ember work | Required behavior checks |
| --- | --- | --- |
| Entry / first-run: `AppShell`, `HeaderBar`, `StartingPanel` | Quiet welcome/provider guidance, clear start/resume status; theme startup and recovery feedback | First launch without character is informational, not a red failure; startup/interview input, failure, recovery, reconnect and resume retain current transitions |
| Global header: `HeaderBar` | Ember brand/location/time/version; public command group; propose responsive overflow menu for secondary actions | Start/New Game, Save, Load, Reset, Settings, Toolkit, Update and Exit remain discoverable with existing availability rules; no invented hosted controls |
| Main story: `GameLog`, `MessageCard`, `InputBar` | Approved center composition, readable narration, optional inline media, persistent command composer | Free text, processing lock, multiline/keyboard behavior, errors, history reading, new-message pinning, late image sizing and reconnect |
| Dice: `DiceStrip` | Compact dock above composer, matching buttons and clear local-roll explanation | D20/D12/D10/D8/D6/D4, results and Clear unchanged; do not portray local rolls as authoritative game checks |
| Party / town / combat: `PartyStrip`, `InitiativeTracker`, `CharacterChip`, `AdventureBox` | Right portrait rail; preserve party vs nearby distinction; compact scrollable initiative variant | All NPCs and monsters retained, exact server order and round/turn ownership, long lists, dead/absent/missing-portrait states; preserve adventure/media affordance |
| Character: `CharacterSheet`, `CharacterTooltips` | Approved left identity, XP, vitals, abilities, weapons/ammunition, saves/features/traits/background/currency | Every current field and tooltip retained, long names/content, no-character state, correct existing calculations; keyboard equivalents for hover |
| Inventory: `InventoryTab` | Consistent dense readable lists, sections, currency/storage entry and search surface | Existing categories, equipment/quantity indicators, filters/search/clear, empty result, storage access; no new equip/drop rules or buttons without existing handlers |
| Spells and magic: `SpellsTab` | Spellcasting summary, slots, spell groups, prepared badges, scrolls/potions/magic items | Non-caster, exhausted slots, charges, descriptions and long lists; do not add casting actions to display-only data |
| NPC information: `NpcsTab`, `NpcDetailModal`, `StatsTooltip` | Ember list/detail/tooltip system with retained portraits | NPC selection, detail fields and inventory where supported, missing data, overflow, close/focus return |
| Maps: `MapTab`, `MapModal`, `ExplorerNotes`, `useMapPanZoom` | Ember frame/chrome and notes; honor existing parchment/night map choice | Fog/reveal rules, markers, pan/zoom/reset/expand, theme persistence, loading/error, close and touch; never expose unrevealed data |
| Journal: `JournalModal` | Full Ember journal surface with readable hierarchy | Existing plot/quest sections and statuses only, long text, empty journal, refresh and modal navigation; no invented quest prompts |
| Storage: `StorageModal` | Styled locations/items/details, useful empty states | Current request/response behavior, list refresh, correct counts and close; no new transfer semantics |
| Settings: `SettingsMenu`, `LocalProviderPanel` | Full-size, sectioned Ember settings dialog or sheet rather than an overflowing tiny dropdown | Provider/key/endpoint flows below, images, all voice options/preview/autoplay, map selection and recovery reachability; preserve persistence owners |
| Save: `SaveDialog` | Consistent description form, primary action and result feedback | Actual save action payload and completion, failures, pending state, duplicate-submit protection |
| Load/delete: `LoadDialog` | Legible save list, selected item, restore/delete confirmation | List, empty/corrupt/unavailable states, selection, restore/reload, delete/cancel, reconnect and stale pending actions |
| Reset: `ResetDialog` | Deliberately distinct danger confirmation within Ember language | Exact existing confirmation and reset payload, cancel, disabled/pending state, server failure and successful restart; no destructive call from merely opening UI |
| Update / exit: `UpdateDialog`, header exit overlay | Version details, update progress/results, exit confirmation and safe-close state | Existing update route/event, error paths, offline exit must not enqueue a stale action, blocked browser close fallback |
| Long-running work: `CompressionOverlay`, `ModuleProgressOverlay`, `StartingPanel` | Consistent accessible status/progress treatment | Existing compression/episodic-upgrade/startup/module-operation states, reconnect restoration, completion/failure; never fabricate a percentage or cancellability |
| Media: `MediaPopup`, `GenerateImageButton`, `TtsButton` | Ember image/video viewer and message tools, loading/failure/retry treatment | Existing asset resolution, upload affordances where reachable, generation association/retry, playback/stop, narration content unchanged, unavailable media and reduced motion |
| Debug: `DebugTab` | Readable dense developer pane, monospace only where useful | Current diagnostics, copy/scroll affordances where present, long output; do not remove public troubleshooting or expose new secrets |
| Toolkit: `module_toolkit.html` | Shared Ember chrome/forms/tables/dialogs across all six tabs, responsive work area | Packs (create/import/export/activate/merge/delete/preview), monster generation/management, NPC generation/management, video processing, embedded builder, module media generator; retain all nested settings/styles/selection/status flows |
| Standalone builder: `module_builder.html` and its serving entry point | Match toolkit builder form, progress, success and error screens | Verify actual route/launch entry during inventory; module input validation, generation status and completion actions; preserve endpoints and job lifecycle |
| Legacy fallback: `game_interface.html`, `/`, launcher | Keep working unchanged during React rollout; document explicit fallback | React/legacy route coexistence, `--ui` options, missing-build fallback; do not change default launch behavior silently |

Toolkit and builder are existing HTML/JavaScript surfaces, not React components.
Theme their existing markup with public shared CSS and targeted accessible HTML
changes; a React rewrite is not a prerequisite. Audit nested popups and dynamically
inserted markup as well as the six visible tabs. Any genuinely unreachable legacy
fragment is recorded with evidence instead of being counted as a completed screen.

The legacy game is a maintained compatibility fallback, not a second simultaneous
Ember implementation. All user game workflows must be available through the Ember
React player before considering its promotion to the launcher default. Marketing,
company websites, billing, account dashboards and private operator panels are not
public game screens and are excluded.

## 6. Public-provider functionality is a release gate

Do this early, before polishing the remaining screens. A settings panel appearing
in a mock browser is not proof that provider selection works.

1. Trace UI → typed Socket.IO event → Python handler → persistence → provider
   resolution → response/store update for all four existing provider values.
2. Record baseline behavior on unmodified public main using an isolated test
   profile. Reproduce failures before attributing them to Ember.
3. Exercise `get_model_provider` / `set_model_provider`, endpoint get/set/test,
   OpenAI and Gemini key get/set, acknowledgments and error handling. Assert exact
   current contracts, not a new optimistic-success protocol.
4. For each provider: select, receive confirmation, close/reopen settings, reload,
   restart the test backend and verify persisted selection. Check rejected saves,
   disconnect mid-save, timeout and successful retry without stuck controls.
5. Local/custom: URL/model editing, optional key, blank-keeps-existing-key behavior,
   saved/unsaved endpoint test semantics, invalid URL, unreachable endpoint,
   authentication failure, model mismatch and success. Preserve supported server
   configuration; don't promise every compatible provider works without testing.
6. Key forms never echo stored secrets. Verify DOM cleanup, masked status, no
   secrets in logs, traces, screenshots, git or browser storage. Use synthetic
   credentials for deterministic tests and the existing secure persistence path.
7. Use real Python handlers with temporary settings/key storage and a controllable
   local provider stub for CI persistence/error tests. Extend the browser fixture
   to implement writes and failures instead of returning canned getter-only state.
8. Separately perform opt-in real-provider smoke tests with approved credentials
   and a bounded cost: configure, start/resume and complete a free-text turn through
   each supported provider available for testing. Restore test settings afterward.
   Report unavailable providers as unverified, not passed. No production campaign
   mutation or paid call is authorized by this planning document.

If the audit finds a backend defect, document the runtime reproduction and make
the smallest separately tested fix. Do not bury provider/runtime fixes in CSS work.

## 7. Responsive and accessibility plan

- Preserve existing public phone behavior before changing it; do not import the
  private mobile shell or assume its events exist. Coordinate with any ongoing
  mobile work before overlapping changes.
- Reference desktop: 1586×992. Also review 1920×1080, 1440×900, 1366×768 and
  1024×768. At intermediate widths, prototype collapsible side panels before
  compressing text or hiding actions; preserve selection and scroll position.
- Phone checks: 390×844, 360×800, 844×390 landscape, plus 760/761px boundary checks.
  Initially scope the desktop layout away from small screens. Apply the shared
  visual language to responsive forms/dialogs without removing current behavior.
  Any redesigned phone navigation requires its own reviewed mockup and tests.
- Every panel/action remains reachable by keyboard and touch. Test virtual-keyboard
  resize, safe areas, scroll locking, orientation changes and large text/200% zoom.
- Dialogs: focus entry/trap/return, Escape where safe, labelled title, correct
  stacking and background inertness. Tabs: arrows/Home/End, associated panels.
- Tooltips need focus/touch alternatives; errors and connection/turn status need
  text and appropriate live announcements. Do not announce the whole transcript
  repeatedly on hydration. Measure contrast; document any reference adjustment
  needed for readability instead of claiming both unchanged pixels and compliance.

## 8. Delivery phases and review checkpoints

Each phase has a focused commit or PR, screen captures, behavior evidence and a
short change summary. Do not mark an entire phase complete on build success alone.

| Phase | Work | Exit gate |
| --- | --- | --- |
| 0 — Baseline and contract audit | Refresh main; run both existing player entry points; complete screen/state manifest, current provider audit, baseline screenshots/tests, public-asset/license review | Reachable surfaces mapped, existing failures recorded, isolated test data ready |
| 1 — Visual foundation and mockups | Shared tokens/fonts/primitives/portal scope; public header, settings, inventory/spells, dialog, combat and toolkit mockups | Owner can inspect representative full screens and intentional differences before broad implementation |
| 2 — Main desktop port | Reconstruct Ember layout on public owners; retain local header, startup, hydration, typed turn handling, optional inline images | Personally reviewed reference-size render; command/combat/reconnect/media tests pass |
| 3 — Local settings and first-run | Complete public settings/voice/recovery presentation and provider verification matrix | Writes, persistence, restart, endpoint failures and accessible recovery verified; real-provider limits documented |
| 4 — Every in-game panel | Inventory, spells, NPC detail, journal, storage, maps, tooltips, media and debug | All screen-manifest rows have inspected populated and edge-state captures; no lost fields or actions |
| 5 — Lifecycle and modal family | Save/load/delete/reset/update/exit, startup/interview and long-operation overlays | Safe confirmations, correct callbacks, progress/reconnect/failure tests; disposable-profile lifecycle walk |
| 6 — Toolkit and builder | All six tabs, nested dialogs, standalone entry, progress/error/results | Each existing workflow audited and exercised safely; no public authoring endpoint regression |
| 7 — Responsive and accessibility | Widths, zoom, keyboard/touch, phone parity, any separately approved responsive redesign | No inaccessible action, unintentional overflow, trapped focus or composer loss |
| 8 — Final visual/release gate | Rebase/merge latest public main safely, rerun affected gates, audit public diff, documentation and rollback | Reviewable public PR with all acceptance evidence; no automatic main push or default-launch switch |

## 9. Personal visual-quality loop

1. Fix browser version, viewport, device scale, font readiness, seeded data and
   media dimensions. Save source/reference and actual captures separately.
2. Personally inspect the 1586×992 render against the locked reference, using
   side-by-side and overlay/diff views. Check column boundaries, header, font
   sizes/weights/line breaks, spacing, rules, controls, image placement and scroll.
3. Correct discrepancies and repeat. Never update a golden just to hide a
   regression. Produce a differences register for intentional public actions,
   artwork, accessibility changes and unavoidable font/raster reconstruction.
4. For additional screens, first approve an Ember mockup/spec, then inspect the
   actual browser implementation against that target. Review error/pending/empty
   states too, not only photogenic populated screenshots.
5. Repeat at laptop/phone/zoom sizes and after integration from newer main.
   Platform screenshot equality and conceptual fidelity are separate claims.
6. Store reviewed browser goldens, capture commands, measured geometry and a
   signed-off checklist in the public branch. Final report states precisely what
   was personally inspected and what remains unverified. No unsupported “100%”.

## 10. Functional verification and release evidence

- Baseline and post-change: `npm ci`, `npm run build`, `npm run lint`,
  `npx vitest run` from `web/frontend`; record inherited failures separately.
  Use default public/local build as the primary gate. If supported build-time
  edition switches remain, check them without importing private server behavior.
- Existing browser/semantic tests remain. Add explicit Ember visual and all-screen
  flows. Old React-vs-legacy pixel geometry describes the old UI: keep it for the
  fallback/baseline, split semantic invariants from intentionally changed pixels,
  and document the transition rather than weaken old thresholds indiscriminately.
- Backend tests cover any touched runtime and contract seams, provider persistence,
  save/restore/reset and media/toolkit handlers. Run against temporary campaigns,
  throwaway asset packs and settings; restore/delete only named test fixtures.
- Full local journey: no key → settings → configured provider → new game/interview
  → play → combat → inventory/spells/NPC/map/journal/storage → save → reload → load
  → resume → disconnect/reconnect → exit. Separate disposable journey covers reset,
  update and authoring operations. Verify no duplicate action delivery.
- Browser coverage: deterministic Chromium goldens plus Firefox/WebKit functional
  checks where supported; Windows/macOS/Linux font/build/static-path checks before
  claiming cross-platform release quality. Record unavailable environments.
- Performance: compare baseline bundle sizes, input responsiveness, long transcript
  and large roster scrolling, image loading and listener counts; no rendering
  entire huge media lists unnecessarily or new mandatory network/font requests.
- Handoff artifacts: screen/state checklist, reference-to-render differences,
  provider matrix, test commands/results, accessibility findings, migration notes,
  license/provenance list and known limitations. Include `git diff --check` and a
  staged-file audit excluding secrets, private code, generated saves and logs.

## 11. Risks, rollback and definition of done

Main risks: donor dependencies on hosted-only code; hidden local actions; themes
missing portals or toolkit-generated markup; different public mobile architecture;
unlicensed/private fixture assets; tests that fake provider success; ongoing main
and mobile work; changing display into unsupported gameplay actions.

Mitigation: public-owned adapters, explicit inventory and contract tests, themed
portal root, independently reviewed responsive work, asset audit, real-handler
provider tests, small commits and repeated upstream integration. Keep legacy route
and launcher selection intact. Roll back by reverting scoped public UI commits;
there should be no data migration to undo. Do not roll back unrelated newer main
fixes or delete user settings/saves to recover the old appearance.

Done means every reachable public screen above has an Ember implementation or an
explicitly documented compatibility role; every current function remains reachable;
all required visual/functional gates have evidence; missing real-provider/platform
checks are disclosed; no private code/history has entered public; and the owner
has inspected the final branch/PR. This document alone does not mark the port done.
