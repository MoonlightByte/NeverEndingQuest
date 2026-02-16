## Why

Save discovery and restore are currently scoped to the active module directory, which makes campaign switching workflows brittle when operators need to jump between archived worldlines in different modules. We need module-agnostic save discovery and safe cross-module restore routing now to support reliable GUI-first campaign orchestration.

## What Changes

- Add a global save catalog that discovers saves across all module save directories and returns normalized metadata for GUI listing.
- Add restore routing that can restore a selected save regardless of the currently active module.
- Add explicit source-module and memory-package presence fields in save list payloads so operators can see restore parity at selection time.
- Add strict path validation for cross-module restore targets to prevent unsafe path traversal or accidental restore from unsupported locations.
- Preserve existing module-local behavior as a compatibility path for legacy callers.
- Explicit non-goals for this change:
  - No campaign zip export/import (covered by a separate change).
  - No changes to save file format beyond additive metadata fields.
  - No changes to gameplay mechanics, combat flow, or LLM behavior.

## Capabilities

### New Capabilities
- `campaign-save-global-index`: Discover, normalize, and present save metadata across all module save directories.
- `campaign-restore-routing`: Restore selected saves from any module directory using validated routing inputs and existing restore safety checks.

### Modified Capabilities
- None.

## Impact

- Affected code: `updates/save_game_manager.py`, `web/web_interface.py`, and `web/templates/game_interface.html`.
- APIs: additive action payload fields and response metadata for save listing and restore selection.
- Dependencies/systems: no new external dependency; relies on existing save metadata and memory package hooks.
- Rollout risk: medium, because restore routing touches state mutation paths; mitigated by strict target validation, preserving existing preflight memory checks, and compatibility fallback.
- Fallback strategy: keep module-local save listing and existing restore entrypoint available if global index feature flag/path fails.
- Merge-safety/SP-MP impact: extension-first changes with minimal host-file hooks; behavior remains backward compatible for single-player and tabletop modes.
