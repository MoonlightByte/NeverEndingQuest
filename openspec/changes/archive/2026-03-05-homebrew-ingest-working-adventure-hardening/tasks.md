## 1. Failed Ingest Cleanup Hardening

- [x] 1.1 Add CLI controls in `scripts/homebrew_ingest_dev.py` for failed-artifact cleanup (`--cleanup-failed` default enabled, `--no-cleanup-failed` override).
- [x] 1.2 Implement safe cleanup/archive stage for `status in {"failed", "quarantined"}` runs.
- [x] 1.3 Add guards so cleanup never removes active/registered module directories.
- [x] 1.4 Add structured stage output (`cleanup_failed_ingest`) to JSON report.

## 2. Monster Materialization Script

- [x] 2.1 Create `scripts/homebrew_materialize_monsters.py` with `--module`, `--strict`, and `--dry-run` options.
- [x] 2.2 Read `modules/<slug>/monsters_seed.json`, resolve names against `data/bestiary/monster_compendium.json`, and write `modules/<slug>/monsters/<slug>.json`.
- [x] 2.3 Use deterministic slug normalization aligned with runtime combat lookup.
- [x] 2.4 Emit structured summary: created/skipped/missing counts + missing names + path conflict repairs.
- [x] 2.5 Add auto-repair for path conflicts (directory at JSON target path).

## 3. Ingest Pipeline Wiring for Working Adventure Readiness

- [x] 3.1 Add `monster_materialization` stage in `scripts/homebrew_ingest_dev.py` after strict success + registry verification.
- [x] 3.2 Mark run as degraded when unresolved seed mappings exist (unless strict-materialization mode is enabled).
- [x] 3.3 Keep ingest success/failure semantics explicit and include materialization stage details in final report.
- [x] 3.4 Add provider_generation_allowed flag to final report for cost transparency.

## 4. Cost-safe Media and Prewarm Behavior

- [x] 4.1 Preserve URL-based media extraction behavior and fail-open contract.
- [x] 4.2 Preserve provider portrait generation as explicit opt-in only (`--allow-provider`).
- [x] 4.3 Ensure final report clearly states whether provider generation was permitted.

## 5. Regression Coverage

- [x] 5.1 Add `scripts/test_homebrew_materialize_monsters.py` for deterministic materialization behavior, missing bestiary mapping, and auto-repair coverage.
- [x] 5.2 Add `scripts/test_homebrew_ingest_cleanup.py` for failed/quarantined cleanup behavior and safety guards.
- [x] 5.3 Update/extend `scripts/test_homebrew_ingest_dev.py` for stage wiring and reporting expectations.

## 6. Verification

- [x] 6.1 Run compile checks: `python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_materialize_monsters.py scripts/test_homebrew_ingest_cleanup.py scripts/test_homebrew_ingest_dev.py`.
- [x] 6.2 Run tests: All test suites pass (8 cleanup + 9 ingest + 10 materialize = 27 tests).
- [x] 6.3 Verify readiness artifacts: Module `monsters/*.json` present, auto-repair verified, cleanup tested.
- [x] 6.4 Run `openspec validate homebrew-ingest-working-adventure-hardening` -> valid.
