# GUI Builder Module Workflow UI Ordering

## Builder Review Draft

Purpose: define the bounded OpenSpec slice that reorders toolkit tabs and workflow emphasis so module-authoring flows come first and graphic-pack tooling comes second.

This is a builder-facing review artifact for UI ordering only.

## Intent

The toolkit should read as two conceptual sections:

1. `Module Builder`
   - `Generate Module`
   - `Generate Module Media`
2. `Graphic Pack Manager`
   - graphic pack import/create
   - monster manager
   - NPC manager

The next slice SHALL reorder the UI to match that author workflow.

## Evidence Baseline

- In `web/templates/module_toolkit.html`, current top-level tab order still places graphic-pack tools ahead of module-builder flow:
  - `Monster Management & Generator`
  - `NPC Management & Generator`
  - `Module Media Generator`
  - other tabs
- The grep hits show relevant tab anchors around:
  - line ~2111 `Monster Management & Generator`
  - line ~2112 `NPC Management & Generator`
  - line ~2115 `Module Media Generator`
  - line ~2553 `builder-tab`
  - line ~2687 `media-gen-tab`
- Product policy now says module-builder tabs/sub-tabs (`Import`, `Media`) should come first, followed by graphic-pack tooling.

## MUST Contract

- The builder SHALL keep scope limited to toolkit UI ordering, labels, and default workflow emphasis.
- The builder SHALL preserve existing functionality and event wiring for all tabs.
- The builder SHALL make module-builder workflow surfaces appear before graphic-pack tooling.
- The builder SHALL preserve `Module Media Generator` as the primary post-build remediation path for missing module monster/NPC media.
- The builder SHALL NOT remove the existing monster/NPC manager tools.
- The builder SHALL NOT redesign unrelated toolkit functionality.
- The builder SHALL keep the existing aesthetic and structure unless changes are necessary to clarify section ordering.

## SHOULD Guidance

- Prefer minimal HTML/JS ordering edits over CSS-heavy redesign.
- Prefer grouping copy or headings that make the conceptual split obvious: `Module Builder` first, `Graphic Pack Manager` second.
- Preserve any stable tab ids and JS switch logic if possible.
- If a default active tab needs adjustment, prefer making the first authoring step obvious.

## Proposed Step Sequence

### Step 1 - Audit the current tab order and grouping hooks

Confirm exact top-level tab/button order, related tab-content blocks, and any JS assumptions in `switchTab(...)` and initial active state.

### Step 2 - Reorder the workflow surfaces

Implement the approved ordering so module-builder tabs come first and graphic-pack tools follow.

Valid outcome:

- author sees module generation/media flow first
- graphic-pack tools remain available and intact
- post-build handoff path aligns with `Module Builder -> Module Media Generator`

### Step 3 - Add focused UI contract coverage

Add source-level or targeted tests/checks that prove ordering and default emphasis without requiring broad end-to-end browser automation unless already present.

### Step 4 - Verify rendered workflow expectations

Run lightweight checks to confirm the tab order and default-active path match the approved IA.

Acceptance target:

- module builder path is visually first
- module media generation is easy to find as the next step after build
- graphic-pack tools remain present but secondary

## Full Builder Prompt

Implement OpenSpec draft `gui-builder-module-workflow-ui-ordering` Step 1-4 only.

Goal: reorder toolkit UI so `Module Builder` workflow appears before graphic-pack tooling and `Module Media Generator` is positioned as the primary post-build media path.

Allowed files:

- `web/templates/module_toolkit.html`
- minimal supporting JS in the same file if tab-order/default-state handling requires it
- targeted tests or source-contract checks for toolkit tab ordering

Forbidden:

- broad visual redesign
- backend workflow changes
- finisher semantics changes
- gameplay/readiness payload normalization
- removal of existing monster/NPC manager tooling

Required:

- reorder/group toolkit tabs so module-builder workflow comes first
- keep `Module Media Generator` in the module-builder path
- preserve current tab functionality and ids where feasible
- add focused verification coverage for ordering/default path

Edit Strategy: Apply one anchored patch at a time, then re-run syntax checks before the next patch.

Verification:

- if JS changes, run `node --check` on extracted/affected script content or equivalent syntax check path already used in repo
- run any targeted source-contract tests added for ordering
- provide before/after tab order summary

Output:

- exact tab/group ordering implemented
- files changed
- syntax/test outcomes
- any stable ids preserved or changed

## Review Questions

1. Do you want explicit visual section headers for `Module Builder` and `Graphic Pack Manager`, or is pure tab reordering sufficient for this slice?
2. Should the default active tab become the module-builder entry point if it is not already?
3. Should monster/NPC manager labels stay as-is, or should their wording also be tightened to feel more clearly like graphic-pack tooling?
