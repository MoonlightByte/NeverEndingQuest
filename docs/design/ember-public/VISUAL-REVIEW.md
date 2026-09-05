# Ember public visual review — 2026-09-05

Status: initial main-screen review only; not complete-plan acceptance or owner
sign-off. Four Chromium/Linux browser goldens are regression targets, not evidence
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

Additional-screen mockups in the review gallery remain drafts pending explicit
owner approval. Actual additional-screen implementations and their screenshot
comparisons, full runtime journeys and final owner review are still outstanding.
