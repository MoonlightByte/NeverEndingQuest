## Why

The Load dialog currently renders save folders first and archive zips second. Even when an archive zip is newer, it appears at the bottom of the list, which causes operator confusion during live tabletop sessions. We need one recency-ordered timeline that combines both entry types and simple type filters.

## What Changes

- Merge save-folder and archive-zip rows into a single load list model in the GUI.
- Sort entries newest-first across both types using a shared timestamp sort key.
- Add filter controls in the Load dialog: `all`, `save_folders`, `archive_zips`.
- Preserve existing action routing:
  - save folder -> `restoreGame`
  - archive zip -> `restoreArchiveZip`
- Keep delete behavior restricted to save folders only.

## Capabilities

### New Capabilities
- `load-dialog-unified-timeline`: Combined recency-ordered list for saves and archive zips.
- `load-dialog-entry-filters`: Operator-visible filter controls for entry type.

### Modified Capabilities
- `load-dialog-action-compatibility`: Existing restore/delete semantics remain stable under the unified list model.

## Impact

- Affected code:
  - `web/templates/game_interface.html`
  - `web/web_interface.py` (only if additive payload normalization support is required)
- APIs:
  - No required backend contract changes; existing `save_list_response` and `archive_zip_list_response` remain valid.
- Rollout risk:
  - Low to medium (UI behavior update), mitigated via focused regression and action-routing checks.
- Compatibility:
  - Existing save-folder restore path remains unchanged.
  - Existing archive-zip restore path remains unchanged.
  - Delete remains disabled for archive zip entries.
