## Why

Operators in library/tabletop environments need a predictable place to copy campaign archives to USB. Current full-save zip artifacts are generated near save folders, which is harder for non-technical staff to discover quickly. We also need direct restore from zip artifacts so operators can recover campaigns without manual unzip/staging steps.

## What Changes

- Move full-save zip artifact output to a repo-root export directory (`archive_exports/`) with deterministic naming.
- Add archive zip catalog discovery for restore workflows.
- Add secure restore-from-zip pipeline (validate -> stage -> delegate to existing restore).
- Integrate zip restore into existing load/restore flow without introducing a new top-level GUI button.
- Preserve existing folder-based restore and `save_mode=essential` behavior.

## Capabilities

### New Capabilities
- `campaign-archive-root-export`: Full save zip artifacts generated to repo-root archive export folder.
- `campaign-zip-import-restore`: Restore campaign state directly from validated zip artifacts.

### Modified Capabilities
- `campaign-save-zip-portability`: zip output location and operator-facing path guidance updated to root export workflow.

## Impact

- Affected code:
  - `updates/save_game_manager.py`
  - `web/web_interface.py`
  - `web/templates/game_interface.html` (load dialog wiring only)
- APIs:
  - Additive list/restore archive-zip action payloads.
- Dependencies:
  - Existing `zipfile`, existing restore pipeline, existing save metadata.
- Rollout risk:
  - Medium (new restore entrypoint), mitigated via strict preflight validation and fallback to existing folder restore.
- Compatibility:
  - Folder restore remains supported.
  - Essential save behavior unchanged.
