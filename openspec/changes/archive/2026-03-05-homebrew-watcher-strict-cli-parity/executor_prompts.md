# Executor Prompts - homebrew-watcher-strict-cli-parity

## Execution Contract (Strict)

- MUST implement strict watcher mode only; no auto-transform fallback in watcher path.
- MUST enforce ingest-ready gate before watcher ingest starts.
- MUST keep provider generation opt-in only.
- MUST preserve archive + sidecar behavior for watcher flow.
- MUST keep Python-visible text ASCII-only.
- SHOULD keep changes additive and merge-safe.

---

## Prompt 1 - Shared Pipeline Entry

Objective:
Create/confirm a shared ingest pipeline callable by CLI and watcher.

Scope:
- `scripts/homebrew_ingest_dev.py`
- shared helper module (if needed)

Tasks:
1. Extract or formalize a pipeline function that returns stage-level result payload.
2. Keep existing CLI behavior unchanged while routing through shared function.
3. Expose canonical keys for media stage results (`media_extraction`, `media_handles`, `portrait_prewarm`).

Verification:
- `python3 -m py_compile scripts/homebrew_ingest_dev.py`
- Existing CLI dry-run command still works.

---

## Prompt 2 - Strict Watcher Gate + Pipeline Parity

Objective:
Make watcher ingest strict and parity-aligned with CLI for validated markdown.

Scope:
- `web/extensions/module_ingest_watch.py`
- `scripts/homebrew_preflight.py` (read-only integration)

Tasks:
1. Add strict preflight gate (`ready == true`, deterministic structure, required metadata).
2. For gate failures, quarantine/archive and write explicit rejection reason in sidecar result.
3. For gate pass, call shared pipeline entrypoint instead of direct importer shortcut.

Verification:
- `python3 -m py_compile web/extensions/module_ingest_watch.py`
- Unit tests for non-ready rejection pass.

---

## Prompt 3 - Sidecar/Audit Compatibility + Provider Constraints

Objective:
Ensure watcher outputs remain sidecar-audit compatible and provider-safe.

Scope:
- `web/extensions/module_ingest_watch.py`
- `scripts/homebrew_sidecar_audit.py` (if schema keys need sync)

Tasks:
1. Persist canonical stage keys in watcher sidecar under `result`.
2. Keep watcher sidecar path and naming deterministic in `modules/ingest/archive`.
3. Preserve provider opt-in behavior; default watcher run should not trigger provider generation.

Verification:
- `python3 scripts/homebrew_sidecar_audit.py --slug <watcher_ingested_slug> --require-success`

---

## Prompt 4 - Regression and End-to-End Verification

Objective:
Add tests and prove watcher/CLI parity for validated markdown.

Scope:
- `scripts/test_module_ingest_watch.py`
- optional parity tests in ingest pipeline tests

Tasks:
1. Add strict rejection tests for raw/non-ready markdown.
2. Add parity test for same validated fixture through CLI and watcher.
3. Add sidecar assertions for canonical media keys and status values.
4. Run compile/tests/smoke and OpenSpec validation.

Verification:
- `python3 -m py_compile web/extensions/module_ingest_watch.py scripts/homebrew_ingest_dev.py scripts/test_module_ingest_watch.py`
- `python3 scripts/test_module_ingest_watch.py`
- `python3 scripts/homebrew_ingest_dev.py --strict --dry-run --source <validated_ingest_ready.md>`
- Watcher smoke in `modules/ingest/`
- `openspec validate homebrew-watcher-strict-cli-parity`

Stop after Prompt 4 scope.
