## Why

`web/static/media/npcs` and `web/static/media/monsters` currently behave like a long-lived accumulation bucket for activated packs, generated assets, and older testing output. That makes fallback media effectively unbounded and increases the risk that stale shared portraits leak into active modules when module-local resolution misses.

## What Changes

- Define a strict-cache contract for `web/static/media/npcs` and `web/static/media/monsters` so they are treated as rebuildable runtime fallback, not canonical asset storage.
- Add a deterministic rebuild workflow that clears live static NPC/monster fallback folders and repopulates them only from active packs.
- Add dry-run audit/reporting, backup, and collision/orphan visibility so operators can review fallout before cleanup.
- Preserve existing runtime lookup order while making shared fallback intentionally sparse and easier to reason about.
- Clarify that publishability and readiness continue to rely on module-local media, not shared static fallback.

## Capabilities

### New Capabilities
- `toolkit-static-media-runtime-cache`: Define strict-cache audit, backup, and rebuild behavior for shared static NPC/monster fallback media.

### Modified Capabilities
- `module-publishable-gate`: Publishability requirements MUST remain module-local and MUST NOT treat shared static fallback media as satisfying module media debt.

## Impact

- Affected code:
  - `core/toolkit/pack_manager.py`
  - `web/web_interface.py`
  - `web/extensions/tabletop_socket_handlers.py`
  - media/toolkit maintenance scripts and regression coverage
- Affected systems:
  - graphic pack activation and live fallback rebuild behavior
  - runtime NPC/monster media fallback surface
  - module publication expectations for module-local media
- Merge-safety impact:
  - MUST prefer extension-file or toolkit-path changes and keep host edits minimal.
- SP/MP compatibility impact:
  - No intended SP/MP gameplay contract change; runtime lookup order stays intact while shared fallback becomes cleaner.
- Rollout risk / fallback strategy:
  - Strict-cache rebuild MUST support dry-run and backup before deletion.
  - If rebuild behavior proves unsafe, operators SHOULD be able to restore the backup snapshot and return to the previous fallback contents.
