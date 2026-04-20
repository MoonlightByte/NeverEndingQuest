# GUI Builder Module Workflow UI Ordering

## Why
The toolkit currently emphasizes graphic-pack tooling before the core module-authoring workflow. Product policy is to make the author experience read in this order:
1. `Module Builder` -> `Generate Module`, `Generate Module Media`
2. `Graphic Pack Manager` -> graphic pack import/create, monster manager, NPC manager

This change aligns the UI ordering with that workflow without removing existing tools.

## What Changes
- Reorder toolkit workflow surfaces so module-builder tabs appear first.
- Keep `Module Media Generator` clearly positioned as the primary post-build media path.
- Keep graphic-pack tools available but secondary.

## Capabilities
- Toolkit UI SHALL present `Module Builder` workflow before graphic-pack tooling.
- Toolkit UI SHALL preserve existing functionality and tab wiring.
- Toolkit UI SHALL keep monster/NPC manager tools present but not primary.

## Impact
- Affected code: `web/templates/module_toolkit.html` and minimal supporting JS/test coverage if needed.
- Affected workflows: default author path and post-build media discoverability.
- No backend workflow or finisher semantics changes in this slice.
