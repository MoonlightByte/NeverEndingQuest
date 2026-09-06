# Intermediate-width drawer study — not approved

This is an isolated proposal for the PORT-PLAN section 7 intermediate-width
side-panel experiment. It is not production navigation and does not modify the
React app, phone layout, game rules, providers or stored data. Owner approval is
still required before considering integration.

At 1024 and 1180 pixels, narrow rails keep character and party/initiative access
visible. Opening a rail shows a full-height sheet or people drawer above the
story instead of compressing its reading column. Native modal dialogs provide
background inertness and keyboard trapping. Escape, the close button and backdrop
return focus to the opener. Draft text, selected sample tab, filter and independent
story/drawer reading positions survive opening, closing and resizing.

Canonical public Ember tokens and licensed self-hosted Cinzel/Crimson Text fonts
are loaded from their existing static sources. Artwork is unmodified public
`graphic_packs/photorealistic` imagery. Arden's sample portrait uses the existing
Ranger Marcus asset; this is an illustrative alias, not a production assignment.
The optional Elen portrait belongs inline to a sample narration; it is not a
mandatory header image. Toggle it off to review text-only play.

Only the sample drawers, character tabs/filter, exploration/combat mode, optional
image and local input form are interactive. Dice are labelled visual specimens,
not new gameplay controls. Lifecycle actions, detailed tooltips, authoring tools
and full game logic remain in the actual React implementation. No network/API
writes, inference, local storage or game events occur here.

Run separately from the existing gallery if it is already running:

```sh
NEQ_REVIEW_PORT=4214 node web/frontend/e2e/ember-review-server.mjs
```

Open `http://127.0.0.1:4214/intermediate`. From `web/frontend`, verify:

```sh
NEQ_E2E_INTERMEDIATE=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4214 \
  npx playwright test e2e/ember-intermediate.spec.ts --workers=1
```

The test captures main, character drawer, party drawer, initiative and text-only
states at both widths. These are prototype captures, not approved goldens or a
claim of parity with a reference that only specifies the full desktop layout.

## Bounded review evidence

On 2026-09-05, three Chromium cases passed (1024×768 and 1180×768, plus touch). Assertions
cover Tab wrapping, Escape even from a populated search box, backdrop dismissal,
focus restoration, retained draft/filter/tab selection and independent scroll,
open-drawer resizing, fixed sample initiative order, optional-image removal and
local-only command submission. External requests are blocked and no API/Socket.IO
requests or page errors occurred.
The touch case verifies both drawer openers, close/backdrop focus restoration and
that native modal inertness prevents programmatic focus on the background input.

All ten final captures were personally inspected. The first visual pass retained
Ember's stacked sheet, fine rules, currency and font scale; the next pass replaced
placeholder dice glyphs with the existing public EmberDieIcon paths and ensured
the collapsed portrait strip changes with sample combat mode. Browser checks
caught and corrected native Tab-to-browser-chrome and search-field Escape quirks.

| Width | Resting view | Left drawer | Right drawer | Combat | No image |
| --- | --- | --- | --- | --- | --- |
| 1024 | [Main](captures/1024-main.png) | [Sheet](captures/1024-sheet.png) | [Party](captures/1024-party.png) | [Initiative](captures/1024-initiative.png) | [Text](captures/1024-text-only.png) |
| 1180 | [Main](captures/1180-main.png) | [Sheet](captures/1180-sheet.png) | [Party](captures/1180-party.png) | [Initiative](captures/1180-initiative.png) | [Text](captures/1180-text-only.png) |

Remaining decision: the owner must review this tradeoff—more reading space while
closed, temporarily obscured story while a drawer is open. This prototype does
not constitute approval, production integration, phone redesign or full parity.
