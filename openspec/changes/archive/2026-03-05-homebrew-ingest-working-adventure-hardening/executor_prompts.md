## Kimi Builder Execution Prompts - homebrew-ingest-working-adventure-hardening

Use this file as the implementation handoff for `tasks.md`.

---

## Execution Contract

- MUST preserve tabletop fail-closed monster runtime policy.
- MUST keep provider image generation opt-in only (`--allow-provider`).
- MUST keep Python-visible text ASCII-only.
- MUST use additive, merge-safe changes.
- SHOULD keep cleanup as archive-first (not destructive delete) by default.

---

## Prompt 1 - Failed Ingest Cleanup Stage

Implement tasks 1.1-1.4.

Scope:
- `scripts/homebrew_ingest_dev.py`

Requirements:
- Add cleanup flags (`--cleanup-failed` default true, `--no-cleanup-failed`).
- Add stage `cleanup_failed_ingest` for failed/quarantined runs.
- Move failed module dir to `modules/ingest/archive/failed_<timestamp>_<slug>/`.
- Guard against removing active/registered module dirs.
- Include cleanup result in JSON report.

Verify before moving on:
- `python3 -m py_compile scripts/homebrew_ingest_dev.py`

---

## Prompt 2 - Monster Materialization Script

Implement tasks 2.1-2.4.

Scope:
- `scripts/homebrew_materialize_monsters.py` (new)

Requirements:
- Load `monsters_seed.json` for module.
- Resolve entries against `data/bestiary/monster_compendium.json`.
- Write module-local `monsters/<slug>.json` files.
- Support `--module`, `--strict`, `--dry-run`.
- Emit structured summary (created/skipped/missing + names).

Verify before moving on:
- `python3 -m py_compile scripts/homebrew_materialize_monsters.py`

---

## Prompt 3 - Pipeline Wiring for Working Adventure Readiness

Implement tasks 3.1-3.3 and 4.1-4.3.

Scope:
- `scripts/homebrew_ingest_dev.py`
- Optional minor touch in helper scripts only if required for report clarity

Requirements:
- Invoke monster materialization after strict success + registry verify.
- Report `monster_materialization` stage in final output.
- Mark run degraded when unresolved mappings exist (unless strict mode for this stage).
- Keep media extraction URL-based and fail-open.
- Keep provider portrait generation disabled unless explicit `--allow-provider`.
- Report whether provider generation was allowed.

Verify before moving on:
- `python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_materialize_monsters.py`

---

## Prompt 4 - Regression Tests and Final Verification

Implement tasks 5.1-6.4.

Scope:
- `scripts/test_homebrew_materialize_monsters.py` (new)
- `scripts/test_homebrew_ingest_cleanup.py` (new)
- `scripts/test_homebrew_ingest_dev.py` (update)

Required final commands:
- `python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_materialize_monsters.py`
- `python3 scripts/test_homebrew_materialize_monsters.py`
- `python3 scripts/test_homebrew_ingest_cleanup.py`
- `python3 scripts/test_homebrew_ingest_dev.py`
- `python3 scripts/homebrew_ingest_dev.py --source "modules/ingest/prepared_night_of_the_living_dead.md" --strict --no-prewarm --json`
- `openspec validate homebrew-ingest-working-adventure-hardening`

Smoke acceptance checklist:
1. Failed/quarantined ingest does not leave module slug under `modules/`.
2. Successful strict ingest creates `modules/<slug>/monsters/*.json`.
3. Module is registered and playable without monster-missing combat failures.
4. Provider generation remains opt-in.
