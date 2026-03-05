## Why

Homebrew ingest can currently leave failed/quarantined module folders in `modules/`, which creates clutter and operator confusion. A second gap is combat readiness: ingest writes `monsters_seed.json`, but tabletop fail-closed combat requires module-local monster stat files under `modules/<slug>/monsters/*.json`.

For practical gameplay testing, we need a deterministic path that produces a clean, working module without requiring paid media generation.

## What Changes

- Add failed-ingest cleanup handling to prevent orphan module folders from quarantined/failed runs.
- Add deterministic post-ingest monster materialization from bestiary into module-local `monsters/*.json` files.
- Keep media extraction URL-based and provider portrait generation opt-in only.
- Expose stage-level reporting so operators can see cleanup/materialization outcomes clearly.

### Non-goals

- No change to tabletop fail-closed combat policy.
- No auto-enabling provider image calls.
- No redesign of importer architecture.

## Capabilities

### New Capabilities
- `homebrew-ingest-failed-artifact-cleanup`: failed/quarantined ingest runs do not leave litter in `modules/`.
- `homebrew-ingest-monster-materialization`: successful ingest materializes module monster JSON files from bestiary seeds.

### Modified Capabilities
- `homebrew-ingest-media-cost-guard`: media stages remain usable without provider image costs; provider remains explicit opt-in.

## Impact

- Affected code:
  - `scripts/homebrew_ingest_dev.py`
  - `scripts/homebrew_materialize_monsters.py` (new)
  - Optional small glue updates in `core/importers/homebrewery_importer.py` if needed
- Runtime/ops behavior:
  - Cleaner `modules/` after failures.
  - Better first-run combat readiness for ingested modules.
  - No forced paid portrait generation.
- Risks:
  - Cleanup logic could remove wrong folders if not guarded.
  - Materialization could fail if seeds do not map to bestiary entries.
- Mitigations:
  - Registry/safety guards before cleanup.
  - Deterministic report of unresolved monster mappings.
  - Fail-open for non-critical media stages, strict behavior optional for monster materialization.
