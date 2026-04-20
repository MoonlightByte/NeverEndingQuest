# Tasks: GUI Builder Module Workflow UI Ordering

## 1. Ordering Contract
- [x] 1.1 Confirm the current top-level tab order, grouping, and active-state assumptions.
- [x] 1.2 Define the final approved ordering for `Module Builder` and `Graphic Pack Manager` surfaces.

## 2. UI Implementation
- [x] 2.1 Reorder/group module-builder workflow surfaces ahead of graphic-pack tooling in `web/templates/module_toolkit.html`.
- [x] 2.2 Keep `Module Media Generator` positioned in the module-builder workflow.
- [x] 2.3 Preserve existing tab ids and event wiring where feasible.

## 3. Regression Coverage
- [x] 3.1 Add focused ordering/default-path source-contract coverage.
- [x] 3.2 Verify monster/NPC manager tooling remains present and reachable.

## 4. Verification
- [x] 4.1 Run relevant syntax checks for changed template/JS content.
- [x] 4.2 Run targeted tests or source-contract checks.
- [x] 4.3 Capture a before/after tab ordering summary for review.
