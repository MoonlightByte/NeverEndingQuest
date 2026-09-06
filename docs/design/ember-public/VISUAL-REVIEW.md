# Ember public visual review — 2026-09-05

Status: main and additional-screen review receipts are now in HANDOFF.md and
ACCEPTANCE-MATRIX.md; neither complete-plan acceptance nor owner sign-off is
claimed. Four Chromium/Linux browser goldens are regression targets, not evidence
of pixel equality with the approved concept.

Personally inspected populated renders at 1586×992, 1920×1080, 1440×900 and
1366×768. The reference-sized composition retains the left stacked character
sheet, central transcript with optional message-owned image, bottom dice/input,
and right party/nearby rail. At shorter heights, lower sheet/transcript content
extends into independent scroll areas; complete keyboard/zoom review remains open.

## Reference differences and disposition

| Difference | Disposition |
| --- | --- |
| Public Start/Save/Load/Reset/Settings/Toolkit/Exit instead of hosted account controls | Intentional preservation of public functionality; do not remove to imitate pixels. |
| Original public portraits, DM logo and scene art | Preserved assets; no regeneration. Fixture portrait assignments are synthetic, not production changes. Square scene art is contained rather than cropped. |
| Time-of-day thumbnail, location IDs and Nearby separator | Existing information retained or membership clarified; needs owner review as an intentional public adaptation. |
| Font glyphs, line breaks, icon shapes and surface texture | Reconstruction differences remain. Self-hosted Cinzel/Crimson and SVG icons are not proven identical to the generated concept. Further refinement remains open; not classified as inherently unavoidable. |
| Missing concept-only footer label | Production does not display “DESKTOP CONCEPT • SAMPLE STATE.” |

Reference geometry assertions at 1586×992 require story x≈471, people x≈1284
and composer y≈858 within 2–3px. Passing those measurements alone does not prove
typography, colors, borders or complete visual parity.

## Reproduce

From `web/frontend`, build with `npm run build`, then in a separate terminal:

```sh
NEQ_E2E_PORT=4204 NEQ_E2E_EMBER_VISUAL=1 node e2e/mock-server.mjs
```

```sh
NEQ_E2E_EMBER_VISUAL=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:4204 npx playwright test e2e/ember-visual.spec.ts --workers=1 --output=test-results/ember-visual
```

Four browser baselines live in `web/frontend/e2e/ember-visual.spec.ts-snapshots/`.
Tests wait for fonts and decoded media, check page overflow and image placement,
and verify the no-image state has no reserved image container. Baselines were
generated, personally inspected, then passed a separate run without updates.
All six checks pass, including a 1366×768 reachability test that scrolls to the
background feature, story continuation and final nearby character while checking
that the composer and Journal remain in the viewport.
Do not update snapshots merely to accept a regression.

Additional-screen mockups in the review gallery remain subject to explicit owner
approval. Actual panels, dialogs and workbenches are now implemented; personally
inspected captures and the remaining full-state/live/platform gates are listed
in HANDOFF.md and ACCEPTANCE-MATRIX.md.

The final provider status pass corrected inherited low-contrast dark green/red
to muted sage/peach on Ember desktop (9.79:1 / 8.35:1 against the lighter modal
gradient stop) and increased status text to 16px. The browser verifies PASS/FAIL
contrast and preserved phone fallback; this is not whole-product accessibility
certification. [Reviewed error state](captures/review-provider-error.png).
Main goldens passed again unchanged after this correction. The exact locked
reference and documentation provenance now live alongside this file.

## Additional edge-state pass

Personally inspected full-save, selected Load, reset confirmation, failed module,
failed compression and long initiative browser states. Load's outer card was
Ember, but its inner list retained legacy green/blue colors, sans type and an
unused `.selected` selector. The correction styles the actual `aria-pressed`
state. A new assertion then caught the general dialog-button hover rule winning
over that correction; excluding save cards fixed the final border/filter mismatch.
An independent reviewer inspected the corrected selected/hover capture and
closed this bounded visual review. [Final selected Load](captures/review-load-selected.png).

The 20-combatant capture exposed legacy colors and tiny ROUND text in the combat
badge. Desktop-only semantic styles now use the shared Ember palette/Crimson
type; the round value and original phone caption are browser-asserted. Personally
inspected the final [scroll-to-last-combatant capture](captures/review-combat-overflow.png).
Combat list scrolling and the disabled processing composer remain intact.

The separate [intermediate-width study](intermediate/README.md) preserves Ember's
palette, stacked sheet and optional inline imagery with collapsible drawers.
Personally inspected 1024 main/sheet and 1180 initiative against the reference.
It deliberately changes layout at narrower widths, so it is a proposal for owner
review, not reference-raster equality or approved production navigation.
