# Design: GUI Builder Module Workflow UI Ordering

## Context
Current toolkit ordering still makes graphic-pack tooling feel like the primary surface. The approved IA is:
- `Module Builder`: `Generate Module`, `Generate Module Media`
- `Graphic Pack Manager`: graphic pack import/create, monster manager, NPC manager

The UI should reflect that author workflow while preserving the current tooling.

## Goals
- Make module-authoring workflow visually first.
- Make `Module Media Generator` easy to find as the next post-build step.
- Preserve existing tab functionality and stable wiring.

## Non-Goals
- Backend workflow changes.
- Finisher semantics changes.
- Gameplay/readiness payload normalization.
- Removal of existing monster/NPC manager tools.

## Decisions

### Decision: Module Builder SHALL appear before Graphic Pack Manager
Top-level toolkit ordering SHALL present module generation/media surfaces before graphic-pack tooling.

### Decision: Existing functionality SHALL remain intact
Tab ids, event wiring, and existing tooling behavior SHALL be preserved wherever feasible.

### Decision: Module Media Generator SHALL remain the post-build media path
The reordered UI SHALL reinforce `Module Builder -> Module Media Generator` as the primary post-build remediation flow.

## Architecture
- Reorder/group relevant tabs and labels in `web/templates/module_toolkit.html`.
- Keep supporting JS changes minimal and localized to preserve current switching behavior.
- Add focused ordering/default-path verification rather than broad browser automation unless already available.

## Risks / Trade-offs
- Reordering can break tab assumptions if ids or active-state logic are changed carelessly.
- Pure reordering without minimal grouping copy may still feel ambiguous; any copy changes should remain minimal.

## Migration Plan
1. Audit current tab order and active-state assumptions.
2. Reorder/group module-builder surfaces ahead of graphic-pack tools.
3. Add focused source-level verification for ordering/default emphasis.
4. Verify the rendered workflow order.

## Verification Plan
- Run syntax checks for any changed JS embedded in `web/templates/module_toolkit.html`.
- Run targeted source-contract tests if added.
- Produce a before/after tab ordering summary.
