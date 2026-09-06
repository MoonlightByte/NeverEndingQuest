# Ember workbench — dialogs, help and keyboard review

The public Toolkit and standalone Builder use the shared Ember presentation,
not a React rewrite or private hosted implementation. Desktop prompts now use an
explicit Promise API; native `window.alert` and `window.confirm` are not replaced.
Below 1024px, that API retains the original native prompt text and presentation.

## Implementation

- All six Toolkit tabs have tab/tabpanel relationships, roving focus and
  Arrow/Home/End navigation through the existing click-owned loaders.
- Existing help text works with hover, focus and touch; the popup is hoverable,
  supports Escape and is removed when its panel becomes unavailable.
- 73 Toolkit alerts and seven confirmations, plus standalone Builder Cancel,
  await `EmberDialogs`. The shared queue renders safe text, preserves line breaks,
  settles canceled/removed prompts, and uses the existing stack's inertness,
  scroll lock and focus return. Confirm starts on Cancel, not Continue.
- Callers retain operation ownership. Confirmed pack/NPC/generation targets are
  snapshotted/rechecked; duplicate prompts are guarded. Builder cancellation uses
  a local generation epoch, live connection and known-running state. Disconnect
  invalidates an old confirmation without permanently losing cancellation after
  reconnect. Existing server job contracts are unchanged.
- The standalone page explicitly includes the same public static helper. The
  exact-template browser tests caught this missing include; it is now present.

The public export success path had an unrelated bestiary guard referencing an
undefined `jobId`. Root reproduced the failure on committed source with a stub
successful export response: `ReferenceError: jobId is not defined` followed by a
generic error alert. Removing that stray guard restores the original ZIP choice;
tests assert the exact export payload and both Continue/Cancel continuations.
No real pack generation or download was executed by these tests.

## Truthful compatibility boundaries

The existing backend Merge endpoint returns success without doing a merge. The
reachable button is now disabled with a readable, associated explanation rather
than offering a misleading success flow. Its route and old compatibility dialog
remain untouched. Implementing pack merging is not smuggled into this UI port.

`editMonster`, `regenerateMonster` and `deleteMonster` contain pre-existing
coming-soon code but have no callers or rendered button bindings. Repository-wide
identifier tracing and the actual monster-list builder confirm they are dead
fragments, not missing reachable screens. They remain unchanged in functionality.

## Verified evidence

- **13 prompt browser cases pass**: text/queue/safe cancellation and stale DOM,
  nested validation/focus/draft preservation, actual delete cancellation and
  stale target, native phone prompts, exact export payload and both ZIP choices,
  plus six Builder cases across both templates. Builder cases cover duplicate
  prompts, reconnect, terminal state and a replacement job with zero/one exact
  `cancel_build` emissions as appropriate.
- **10 existing workbench/accessibility cases pass**: six-tab/standalone desktop
  and phone presentation, shared fonts, nested modal lifecycle, actual registered
  generation-result handlers and keyboard/pointer/touch help.
- Both inline application scripts parse and shared helper syntax passes. Standalone's CRLF
  format is retained; `git -c core.whitespace=cr-at-eol diff --check` passes.
- Independent reviews closed hover-popup, Builder reconnect and standalone
  helper-delivery findings. Root personally inspected desktop/phone tabs/help,
  nested validation and an ordinary actual pack-delete confirmation screenshot.

Tests serve exact templates/shared assets with intercepted HTTP and a Socket.IO
stub that records emissions and invokes the registered handlers. They do not
prove real generation or process cancellation. The standalone helper is **not**
injected by the fixture. The separate actual-Flask entrypoint probe now checks
both rendered pages include the helper once, as well as serving its exact bytes;
its post-commit result passed on `9727a86` and is recorded in HANDOFF.md.

From `web/frontend`:

```sh
NEQ_E2E_WORKBENCH=1 npx playwright test e2e/ember-workbench.spec.ts e2e/ember-workbench-accessibility.spec.ts e2e/ember-workbench-prompts.spec.ts --workers=1
```

Local root evidence directories under
`/mnt/e/neq-ember-entrypoint-probes.CoTVdyp2/`:
`workbench-integrated-reviewed` and `workbench-prompts-root-final`.
The previous integrated run expected the formerly clickable Merge placeholder;
its two failures were corrected by testing the intentional unavailable state,
not by re-enabling a nonfunctional action. Other workflow assertions remain.

Additional dialog owner approval, real authoring jobs and platform checks remain
open. These are bounded implementation receipts, not final visual acceptance.
