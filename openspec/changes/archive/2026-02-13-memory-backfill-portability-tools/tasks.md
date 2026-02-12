## 1. Source Selection Backfill

- [x] 1.1 Extend `scripts/backfill_memory_db.py` with `--sources` CSV parsing.
- [x] 1.2 Validate selector labels (`journal`, `conversation`, `combat`) and fail fast on invalid values.
- [x] 1.3 Extend `backfill_memory_db_from_histories(...)` to accept source-gating input and skip non-selected channels.
- [x] 1.4 Verify selective ingest preserves idempotency behavior with repeated runs.

## 2. Memory DB Portability

- [x] 2.1 Add export helper that writes DB copy + JSON manifest (version/timestamp/row counts/hash).
- [x] 2.2 Add import helper with manifest/integrity/schema checks before restore.
- [x] 2.3 Implement safe default import behavior (no overwrite unless explicit override flag).
- [x] 2.4 Add import dry-run mode that performs checks but writes nothing.

## 3. Validation and Documentation

- [x] 3.1 Add tests for source selector parsing/validation and selective ingest behavior.
- [x] 3.2 Add tests for export/import manifest validation and non-destructive defaults.
- [x] 3.3 Update `plans/memory.md` and operator docs with portability workflow examples.
- [x] 3.4 Run syntax/test commands and record results in change artifacts.
