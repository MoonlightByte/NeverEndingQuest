# Ember public — action confirmation review

Desktop Restore, Delete Save and Exit now use the shared Ember dialog family
instead of native browser prompts. Existing phone prompt wording and native
presentation remain unchanged. Cancel is the initial focused action; nested
dialogs share the existing portal, inertness, Escape and focus-return owner.

Load/Delete retain exact public action payloads. A confirmation captures the
save folder and checks current connection/save existence before acting. Pending
restore preparation is guarded against duplicate submissions, cancellation,
disconnect, unmount and a save disappearing. Its restart marker is written only
if that operation is still current, so an old canceled request cannot overwrite
a newer marker. Failures remain visible with a retry path. Exit reads current
connection state before emitting, retaining the safe-close fallback.

## Verified receipt

- Full current source unit run: **32 files / 315 tests passed**. Source was
  copied into the existing Linux dependency export for this run, not a fresh
  dependency installation. The new confirmation suite has 12 tests.
- Public build passed; lint reports 18 warnings, no errors. The new LoadDialog
  warning concerns an intentional operation-generation ref in effect cleanup;
  copying its old value would defeat late-response invalidation.
- Four scripted Chromium confirmation cases passed: nested Restore/Delete
  cancellation and exact focus return, one exact Delete payload, cancellation
  during restart preparation with no action/marker, desktop Exit cancellation
  and native phone Exit preservation.
- Six main visual/containment cases passed alongside them, including all four
  desktop goldens without baseline changes and optional-inline-image behavior.
- Independent source review found no remaining bounded confirmation finding.

Root personally inspected Restore, pending Restore and Exit browser screenshots,
and re-compared the actual main screen with the locked reference. The dark/brass
panels, readable body type, controls and focus treatment follow the shared Ember
language. Additional dialogs have no separately owner-approved raster reference;
this is not a 100% pixel-parity claim or owner sign-off.

Re-run against an isolated scripted preview, **never a real campaign**:

```sh
# from web/frontend, separate terminal
NEQ_E2E_PORT=4213 NEQ_E2E_EMBER_VISUAL=1 node e2e/mock-server.mjs
NEQ_E2E_EMBER_VISUAL=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4213 \
  npx playwright test e2e/ember-confirmations.spec.ts e2e/ember-visual.spec.ts --workers=1
```

Final local captures/results:
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/ember-confirmations-final`.
An earlier run failed only because its fixture process had stopped; all four
tests failed before reaching the page. After confirming that process was terminal,
the fixture was restarted and all ten cases passed. Live server process restart,
paid provider turns and native platform browser-close behavior remain unverified.
