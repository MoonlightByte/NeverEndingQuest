## Context

The ingest pipeline already provides strict validation and quarantine semantics, but it currently has two operational gaps:

1. A quarantined/failed run can leave generated module folders in `modules/`, which looks like a valid module even when not registered.
2. Successful ingest does not materialize module-local monster stat files required by tabletop fail-closed combat loader paths.

We also need to preserve existing cost controls: URL-based media extraction is acceptable; provider portrait generation must remain opt-in.

## Goals / Non-Goals

**Goals:**
- Ensure failed ingest artifacts are cleaned or archived deterministically.
- Materialize module monster JSON files from bestiary for combat readiness.
- Keep paid image generation opt-in only.
- Provide clear stage reporting for operator troubleshooting.

**Non-Goals:**
- No change to core importer room parser behavior.
- No change to fail-closed tabletop runtime combat policy.
- No forced portrait generation.

## Decisions

1. **Archive-over-delete cleanup for failed ingest artifacts**
   - Decision: move failed/quarantined module folders to `modules/ingest/archive/failed_<timestamp>_<slug>/` by default.
   - Rationale: preserves forensic data while removing `modules/` clutter.
   - Alternative: immediate delete. Rejected due to loss of debugging context.

2. **Dedicated monster materialization script**
   - Decision: add `scripts/homebrew_materialize_monsters.py` and invoke it from ingest stage after strict success.
   - Rationale: keeps ingest orchestrator simple and allows independent testing/retry.
   - Alternative: embed materialization directly in importer. Rejected due to coupling and harder recovery workflows.

3. **Bestiary-first deterministic mapping**
   - Decision: resolve monsters from `monsters_seed.json` against `data/bestiary/monster_compendium.json`, then write module-local `monsters/<slug>.json`.
   - Rationale: consistent source of truth and deterministic output.
   - Alternative: LLM-generated monster stat synthesis. Rejected for determinism and compliance risk.

4. **Cost-safe media behavior unchanged by default**
   - Decision: keep media extraction URL-based and keep provider portraits disabled unless explicit `--allow-provider`.
   - Rationale: avoid surprise spend in ingest runs.

## Risks / Trade-offs

- **Cleanup safety risk:** wrong folder archived/deleted.
  - Mitigation: guard on expected slug/path and registry checks; never touch active registered module.
- **Incomplete monster readiness:** seeds contain names not found in bestiary.
  - Mitigation: structured unresolved report with optional strict mode to fail stage.
- **Pipeline complexity increase:** extra stage and reporting.
  - Mitigation: bounded, explicit stage contract and test coverage.

## Migration Plan

1. Add `homebrew_materialize_monsters.py` script and tests.
2. Add failed-ingest cleanup stage in `homebrew_ingest_dev.py`.
3. Add post-success monster materialization stage in `homebrew_ingest_dev.py`.
4. Verify media/prewarm cost-control defaults remain intact.
5. Run compile + targeted tests + ingest smoke.

Rollback:
- Disable new ingest stages with conservative defaults.
- Keep script in repo; stop invoking it from pipeline.

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_materialize_monsters.py`
- Tests:
  - `python3 scripts/test_homebrew_materialize_monsters.py`
  - `python3 scripts/test_homebrew_ingest_cleanup.py`
  - `python3 scripts/test_homebrew_ingest_dev.py`
- Smoke:
  - Strict ingest sample module -> success
  - Confirm `modules/<slug>/monsters/*.json` exists
  - Confirm failed slug does not remain in `modules/`
