## Why

Operators need fully portable campaign save artifacts that can move between machines using existing GUI save workflows, including memory DB state. Current save folders are portable manually, but archive saves do not automatically emit single-file zip artifacts, and reset backup flow does not explicitly guarantee memory-state coverage.

## What Changes

- On existing GUI save action, when save mode is `full` (`Archive Edition`), auto-generate a portable zip artifact in backend with no additional GUI controls.
- Ensure archive zip content is campaign-recoverable across all played modules, including memory parity artifacts.
- Enforce archive zip generation safety and deterministic naming/location for operator backup workflows.
- Enforce explicit failure of archive save when required zip artifact cannot be produced.
- Add reset backup parity so memory state is explicitly captured during nuclear reset backup phase.
- Explicit non-goals for this change:
  - No remote/cloud sync service in this phase.
  - No change to save worldline semantics.
  - No modifications to combat/narration pipelines.

## Capabilities

### New Capabilities
- `campaign-save-zip-portability`: Automatic portable zip generation on archive save with campaign-wide recovery coverage.
- `campaign-reset-memory-backup-parity`: Ensure nuclear reset backup explicitly captures memory state artifacts.

### Modified Capabilities
- None.

## Impact

- Affected code: `updates/save_game_manager.py`, `web/web_interface.py`, `utils/reset_campaign.py`.
- APIs: additive save result metadata/status fields for auto-generated archive zip artifact.
- Dependencies/systems: reuses existing Python zip utilities and existing memory portability helpers.
- Rollout risk: medium, because archive save now has hard dependency on zip generation; mitigated by deterministic artifact pathing and explicit failure messaging.
- Fallback strategy: for non-archive saves (`essential` mode), existing save workflow is unchanged.
- Merge-safety/SP-MP impact: additive extension behavior with minimal host hooks; works for both single-player and tabletop modes.
