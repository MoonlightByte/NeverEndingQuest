## 1. Shared Pipeline Parity

- [x] 1.1 Extract or formalize a shared ingest pipeline entrypoint callable by both CLI and watcher.
- [x] 1.2 Update `scripts/homebrew_ingest_dev.py` to use shared entrypoint without changing CLI behavior.
- [x] 1.3 Ensure shared result payload exposes canonical stage keys needed by watcher sidecar.

## 2. Strict Watcher Gate

- [x] 2.1 Add strict preflight readiness gate in `web/extensions/module_ingest_watch.py`.
- [x] 2.2 Reject/quarantine non-ready markdown with explicit reason codes in sidecar `result`.
- [x] 2.3 Ensure strict gate does not auto-transform or run LLM rewrite.

## 3. Sidecar and Audit Compatibility

- [x] 3.1 Keep watcher sidecar creation deterministic in `modules/ingest/archive/*.result.json`.
- [x] 3.2 Persist shared pipeline stage results to sidecar with canonical media keys.
- [x] 3.3 Confirm `scripts/homebrew_sidecar_audit.py --require-success` passes for watcher-ingested validated markdown.

## 4. Provider and Media Constraints

- [x] 4.1 Preserve provider generation opt-in behavior in watcher parity path.
- [x] 4.2 Confirm default watcher path does not trigger provider generation.
- [x] 4.3 Keep monster/portrait lane boundaries unchanged.

## 5. Regression Coverage

- [x] 5.1 Extend `scripts/test_module_ingest_watch.py` for strict gate rejection and sidecar reason fields.
- [x] 5.2 Add parity test(s) comparing watcher vs CLI results for the same ingest-ready fixture.
- [x] 5.3 Add/adjust media-stage parity assertions (canonical keys and statuses).

## 6. Verification

- [x] 6.1 `python3 -m py_compile web/extensions/module_ingest_watch.py scripts/homebrew_ingest_dev.py scripts/homebrew_sidecar_audit.py scripts/test_module_ingest_watch.py`
- [x] 6.2 `python3 scripts/test_module_ingest_watch.py`
- [x] 6.3 `python3 scripts/homebrew_ingest_dev.py --strict --dry-run --source <validated_ingest_ready.md>`
- [x] 6.4 Watcher smoke: drop validated markdown in `modules/ingest/`, start server, confirm sidecar + module registration.
- [x] 6.5 `python3 scripts/homebrew_sidecar_audit.py --slug <expected_slug> --require-success`
- [x] 6.6 `openspec validate homebrew-watcher-strict-cli-parity`
