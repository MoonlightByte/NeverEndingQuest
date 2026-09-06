# Ember public acceptance matrix — 2026-09-05

This is an evidence inventory, **not final approval**. The implementation is
available on `feat/ember-public-complete`; no public-main publication is approved.
Owner inspection and the remaining gates below prevent claiming the entire plan
complete. Earlier ledger entries describe historical scope, not current omissions.

Sources of truth: `PORT-PLAN.md`, `TRANSITION-GATES.md`, actual source owners,
colocated tests, browser captures and test output. The full unit suite currently
passes 35 files / 333 tests. Browser receipt counts are in `HANDOFF.md` and
[BROWSER-REVIEW.md](BROWSER-REVIEW.md); test existence alone is not a pass.
Chromium/Firefox evidence uses synthetic campaigns. The available frozen WebKit
runtime has partial semantic evidence but fails accurate viewport emulation.

## Screen coverage

All listed React/workbench surfaces have Ember presentation. Legacy is an
intentional compatibility exception, not a second Ember game. `e2e/` below means
`web/frontend/e2e/`; component test names are under `web/frontend/src/components/`.

| Plan surface | Inspected evidence | Remaining acceptance limit |
| --- | --- | --- |
| Entry / first-run | Header/startup/recovery units; 3 real-Flask startup browser cases plus 3 empty-bootstrap cases with reviewed captures and desktop/phone checks | Full live interview/new-game journey and actual operator recovery unverified |
| Global header | `HeaderBar.test.tsx`, `e2e/ember-public.spec.ts`, reference captures; review-only [secondary-action Menu proposal](intermediate/README.md) with five drawer/menu tests | Owner approval of public-control adaptation; new overflow menu not approved or integrated |
| Main story / composer | `log/log.test.tsx`, `e2e/player-shell.spec.ts`, `ember-runtime.spec.ts`, four reviewed visual goldens | Real AI turn and platform typography unverified; raster concept equality not claimed |
| Dice | Distinct SVG dice and local-roll explanation; log tests, responsive draft/roll continuity, main captures | Owner visual approval; no new authoritative roll mechanics |
| Party / town / combat | Server-shaped combat hydration, `ember-runtime.spec.ts`, `ember-npc-media.spec.ts`, populated rail captures | Every dead/absent/long-list state has not received a final owner visual pass |
| Character / abilities | Character/tooltip units, long pinned feature browser test, main captures; reviewed loading/no-character/error bootstrap states | All optional character-field combinations not screenshot-audited |
| Inventory / search | `InventoryViewState.test.tsx`, `ember-inspection.spec.ts`, `ember-preview.spec.ts` | Full live campaign/reset journey unverified; tests use synthetic updates |
| Spells / magic | `spellDetails.test.tsx`, shared reference timeout/retry test, player/NPC/alias-scroll browser tests; non-caster notice and quantity-badge desktop/phone styling checks | All long/absent combinations not visually signed off; no casting actions invented |
| NPC information | All seven detail actions, live quantity/usage/slot updates, nested focus and original portrait browser checks | Full live removal/load journey and each missing-data capture unverified |
| Maps | `MapTab*.test.tsx`, `MapModal.test.tsx`, `useMapPanZoom.test.ts`, two populated browser map tests, expanded/empty captures | Real-device touch and every error presentation not owner-approved |
| Journal | Reviewed loading/empty/error/populated browser captures and units; independent close/reopen retry and hidden-quest checks | Full live quest/reset transition and owner sign-off unverified |
| Storage | Reviewed 4-state browser captures, actual request bindings and units; truthful desktop read-failure message, phone preservation, independent retry | Real storage refresh during a live campaign unverified |
| Settings / providers | Seven browser checks; 25 real handler/SDK/stub tests; 10 settings unit tests; reviewed provider/voice/error captures | Paid inference unverified; old-response-after-new-probe correlation needs a contract decision |
| Save | Browser dialog/intent/full-mode checks; exact payload and offline draft/reconnect ownership unit tests; actual essential/full handler-and-file probe | Full live browser journey and active-turn save queue unverified; owner preview is simulated |
| Load / delete | Selection/hover styling, themed nested confirmations, duplicate/stale/cancel/restart-marker tests; actual valid/corrupt restore and delete/reconnect file probe; [current dialog receipt](DIALOG-REVIEW.md) | Actual process restart and every unavailable state unverified; probe intercepts exit |
| Reset | Exact five-digit confirmation; all pending dismissal paths, duplicate/disconnect/unmount/marker ownership unit checks; browser cancel-without-reset; actual disposable reset and retained-backup probe | No production reset; actual restart and recovery from reset backup unverified |
| Update / exit | Unit callbacks/restart failures/offline exit; Update pending duplicate/cancel/disconnect/unmount/marker ownership tests; browser version/progress surfaces | Actual updating process and platform browser-close behavior unverified |
| Long-running work | `operations.test.tsx`, blocking-overlay/reconnect browser checks; reviewed module failure/blocking and compression failure/nonblocking captures | Real compression/module jobs and every terminal screenshot unverified |
| Media / narration | Original viewer, real upload/static+module persistence, desktop/open-viewer/combat/phone refresh, rejected-upload byte preservation, cache/race/audio tests | No paid image/TTS calls; native file-picker activation and every campaign interleaving unverified; see MEDIA-REVIEW.md |
| Debug | `DebugTab.test.tsx`, populated 64-line browser surface and capture | No formal large-log performance profile |
| Toolkit — six tabs | Ten workbench/tab/help cases plus 13 shared prompt/Builder cases; [dialog review](WORKBENCH-DIALOG-REVIEW.md); actual safe create/export/preview/import/recoverable-delete probe with portrait-byte round trip | Live generation/activation and browser-to-backend authoring unverified; existing no-op Merge now visibly disabled |
| Standalone builder | Actual Flask `/` plus shared assets; exact-template helper delivery and cancellation after reconnect/terminal/replacement; actual incomplete-input/idle-cancel/list probe without jobs | Real module build/completion journey unverified; no new server job-identity contract |
| Legacy fallback / launcher | Actual disposable missing-build503/legacy200/toolkit200, built React coexistence, launcher options/default/freshness probe; nine launcher tests | No native-platform or whole-legacy offline guarantee; default remains legacy |

## Transition gates

| Gate | Current evidence | Not proven by this evidence |
| --- | --- | --- |
| F1 inventory continuity | Query/filter/sort/scroll session owner, unit tab-unmount/server-identity checks, browser polling/tab/breakpoint continuity | Every live reset/load transition |
| F2/A2 media freshness | Actual upload journey across sheet/exploration/open viewer/initiative/phone; matching persisted bytes; 38 party tests including alias/suffix/identity races and existing pack-revision browser checks | Open-viewer integration explicitly injects the named invalidation event; native keyboard/touch file picker and every live reset/load interleaving unverified |
| F3 live NPC details | Stable identity selection and actual socket-listener browser updates to quantities, usage and slots | Every removal/load/reconnect interleaving |
| A1 responsive ownership | Rolls/draft/tab continuity, public boundary browser suite, extra constrained viewports | Native zoom/OS keyboard/safe areas and every duplicated-listener assertion |
| F5 spell identity | Shared resolver; actual Python compatibility-map comparison; player/NPC/scroll browser access; timeout/retry and metadata tests | Exhaustive screenshots of all repository entries |
| A3 audio ownership | Coordinator, pending-owner guards, settings-close and direct-disable tests, bounded cache/revocation | Real paid engines; native speech engines on all platforms |
| A4/F4 overlays | Modal stack/inertness/Escape/focus and pinning tests, toolkit nesting, blocking-operation browser capture | Every possible overlay combination and assistive-technology platform |
| A5 entry points | Actual two-Flask-app route/static probe, eleven valid bundled fonts, missing-build compatibility, narrow shared-token freshness fix | Native OS deployment and full legacy Socket.IO CDN offline behavior |

Independent feature and architecture agents have closed the concrete findings
reported during these implementation batches. That does not close the unverified
items above or substitute for owner approval.

The final operation-ownership suite adds four passing cases in each of Chromium
and Firefox, with all owned Save/Reset/Update packets intercepted. It checks
offline draft preservation, consistent pending Reset dismissal, Reset
disconnect/reconfirmation and Update duplicate/cancel/retry. This is frontend
delivery evidence, not a claim that an actual updater or server restart ran.

## Provider matrix and reproduction

`legacy`, `openai`, `gemini`, `lmstudio` each pass selection/confirmation/browser
reload and real Python persistence/re-import/Socket.IO routing tests. They have
**not** each completed an approved live-provider turn.

Local/custom testing uses the real SDK against a loopback HTTP stub for model
listing, empty list, mismatch warning, authentication failures and chat fallback.
An SDK transport double tests connection failure/timeout then retry. SDK retries
are disabled only in tests to keep failures bounded. Probe inputs do not persist
unless Save is used; blank key retention and secret-status-only responses are
tested with synthetic keys. No real keys or provider responses are in artifacts.

```sh
python -m pytest -q web/frontend/e2e/provider_contract_test.py
python -m pytest -q tests/test_run_web_frontend.py
# Use the game's dependency environment (including Flask-Cors), after npm build:
python web/frontend/e2e/ember_entrypoint_probe.py --temp-parent /path/to/test-volume
```

The probe's parent directory must exist and have room for a tracked export. It
creates its own child, retains it and reports exact HEAD/launcher hash. It never
renames a live build or imports the developer's settings. `/tmp` on this machine
was nearly full; the successful run used a dedicated directory on E: instead.

## Final owner/release decisions

- Inspect the running actual UI, not only gallery images. Additional-screen
  mockups and intentional public adaptations still need explicit owner sign-off.
- Review the delivered [intermediate-width collapsible-panel prototype](intermediate/README.md).
  Five bounded drawer/menu browser cases and independent review pass; it is not approved
  production navigation. The runtime retains public breakpoint ownership.
- Approve any optional endpoint response-correlation contract change separately.
- Approve credentials/cost for opt-in live-provider tests before calling those
  providers verified. [Safe disposable real lifecycle tests](LIFECYCLE-REVIEW.md)
  now pass for handlers/files, but do not prove the full live browser journey.
  No paid/destructive
  production testing or public-main push is authorized by this goal.
- [Bounded baseline/Ember performance comparison](PERFORMANCE-REVIEW.md) now
  measures 400 messages / 80 NPCs with verified served-build provenance. It is
  not field INP, a leak certification or real-device profiling.
- Native platform/browser checks, formal performance and full state-by-state
  screenshot acceptance remain open. Three development-dependency audit findings
  are disclosed in HANDOFF.md; runtime-only npm audit reports zero.

No data migration, user artwork replacement, hosted account requirement, or
launcher-default change is part of the port. To roll back, revert scoped public
UI commits, not the newer public-main history or user saves/settings.
