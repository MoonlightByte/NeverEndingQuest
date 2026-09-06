# Startup, ledger and authoring acceptance pass — 2026-09-05

This supplements, not replaces, the full acceptance matrix. No owner sign-off,
paid inference, production mutation or complete raster parity is claimed.

## Startup and empty character state

Three `ember-startup-states.spec.ts` cases pass against the isolated real-Flask
fixture: pre-start with persisted sample state, startup input authorization, and
failed-start recovery on desktop/phone. Actual Socket.IO frame/request observation
checks that failed startup retains a typed draft without sending a turn or a
recovery action. Recovery controls remain accessible, masked token input is
cleared before capture, and Tab reaches the entire Done button in the viewport.
The start handler is a fixture double; no engine or operator recovery runs.

A separate empty-bootstrap fixture returns the actual public handler's null-data
notice/error shapes. Its three cases cover loading, no-character notice and
missing-player error across Character, Inventory and Spells. The first visual pass
found inherited full-height black/Courier loading presentation and undersized
notice/error text. Desktop now uses compact Ember panels and 18px Crimson with
status/alert semantics. Phone classes, font sizes and roles remain unchanged;
the test explicitly preserves Character loading's 16px Courier exception.

Startup recovery result text now uses 16px Crimson on desktop, with the original
13px phone rendering verified. Neither change alters hydration, game rules,
recovery tokens, cooldowns or provider contracts. Primary and independent agents
personally inspected the final captures. [Empty first-run notice](captures/review-bootstrap-notice.png),
[recovery and keyboard-reachable footer](captures/review-startup-recovery.png).

## Journal and Storage

Nine browser cases pass: loading/empty/error/populated for both desktop dialogs,
plus phone Storage preservation. Actual public response shapes and hidden-quest
filtering are retained. A desktop Storage read failure no longer masquerades as
empty storage; it announces a failure and explains close/reopen retry. Loading
has a status role. Existing phone copy and behavior remain unchanged.

The primary agent personally inspected all eight final desktop card captures.
An independent agent also verified same-page error → close → successful reopen,
exact focus return and exclusion of undiscovered main/side quests. These tests
use an isolated Socket.IO data fixture, not real campaign changes. Its sparse
background is not a whole-screen artwork-parity target. The curated
[Storage error card](captures/review-storage-error.png) is a browser element
screenshot of the actual dialog, not a retouched image.

## Actual safe authoring operations

`ember_toolkit_probe.py` passed against tracked source
`41be31412e1b6ce28323cfcf3aef63a08956ff64` in a fresh disposable export. It uses
actual Flask handlers, PackManager, ZIP files and standalone-builder Socket.IO:

- List, create a synthetic pack, reject duplicate creation without overwriting it.
- Export ZIP and verify manifest plus byte-identical existing public Elen portrait.
- Preview and import that ZIP; verify the imported portrait bytes.
- Reject missing/bad ZIP uploads and missing-pack export.
- Delete only the synthetic packs, retaining recoverable `.deleted` backups.
- Reject incomplete builder inputs, report idle cancellation and list modules;
  no build thread or job starts.

No active pack, user artwork, campaign or developer credentials are changed.
Networking, subprocess jobs and writes outside the disposable child are blocked.
Evidence is retained at
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/neq-ember-toolkit-pb1lyp1f/result.json`.
An independent reviewer inspected the probe, real handlers and retained result.
This is not browser-to-backend authoring, activation, generation, or a full module
build/completion journey.

**Pre-existing functional limit:** `web/web_interface.py:merge_pack` returns a
placeholder success without merging. The design port does not implement pack
merging; this workflow must not be called functionally accepted. No backend merge
semantics were invented or changed in this pass.

## Reproduction

Build `web/frontend` first. Run fixture servers separately, on loopback only:

```sh
# From web/frontend, separate terminals:
node e2e/ember-bootstrap-server.mjs
node e2e/ember-ledger-server.mjs

NEQ_E2E_BOOTSTRAP=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4216 npx playwright test e2e/ember-bootstrap.spec.ts --workers=1
NEQ_E2E_LEDGER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4215 npx playwright test e2e/ember-ledger-states.spec.ts --workers=1

# Point at a separately started ember_runtime_server.py fixture:
NEQ_E2E_REAL_RUNTIME=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4208 npx playwright test e2e/ember-startup-states.spec.ts --workers=1
```

From the public repository root, in the game's dependency environment including
Flask-Cors, use an existing parent with room for a tracked export:

```sh
python web/frontend/e2e/ember_toolkit_probe.py --temp-parent /path/to/test-volume
```

The final frontend source was overlaid into the isolated Linux verification
export: all 31 unit files / 291 tests pass. Build and lint pass with 16 existing
warnings. Ten main-screen visual/interactive tests pass without golden updates.
No unit count or fixture pass proves the remaining live/platform/owner gates.
