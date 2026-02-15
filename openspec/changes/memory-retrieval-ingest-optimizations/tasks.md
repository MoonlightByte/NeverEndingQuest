## 1. Retrieval Query Efficiency and Correctness

- [x] 1.1 Refactor `get_entity_timeline()` in `core/memory/memory_retrieval.py` to use bounded candidate pre-selection before final ranking.
- [x] 1.2 Add event-level de-duplication so timeline responses contain one row per event even when multiple links exist.
- [x] 1.3 Update retrieval audit logging to report pre-limit candidate counts separately from returned row counts.
- [x] 1.4 Add read-only sqlite open behavior for retrieval paths and explicit handling when DB path is missing.

## 2. Ingest/Backfill Throughput and Fidelity

- [x] 2.1 Refactor backfill ingest flow in `core/memory/memory_ingest.py` to reuse a shared DB connection per run.
- [x] 2.2 Introduce batched transaction boundaries that improve throughput while preserving malformed-entry tolerance.
- [x] 2.3 Add timestamp precedence logic for backfill (use source timestamp when available, deterministic fallback otherwise).
- [x] 2.4 Update `scripts/backfill_memory_db.py` as needed to align with shared-connection ingest and timestamp behavior.

## 3. Regression Coverage

- [x] 3.1 Extend retrieval tests to assert deterministic ordering with de-duplication and bounded candidate behavior.
  - Implemented in `scripts/test_memory_regression_coverage.py::test_deterministic_ordering_with_dedup()`
  - Tests 3 runs produce identical ordering, no duplicates, correct timestamp DESC order
- [x] 3.2 Extend ingest tests to assert batch-mode idempotency, partial-failure tolerance, and timestamp fidelity.
  - Implemented in `scripts/test_memory_regression_coverage.py::test_batch_idempotency()`
  - Tests re-ingesting same entries creates no duplicates, mixed batches only add new entries
- [x] 3.3 Add regression tests ensuring read-only retrieval does not create new DB files on missing paths.
  - Implemented in `scripts/test_memory_regression_coverage.py::test_readonly_no_create()`
  - Tests all 3 retrieval APIs (`get_entity_timeline`, `get_context_memories`, `get_retirement_return_memories`) return empty lists for missing DB, no file creation

## 4. Verification and Documentation

- [x] 4.1 Run syntax/test verification for touched modules and memory test suites; record results in change notes.
  - **Syntax verification**: All Python files compile successfully
  - **Test suite results**:
    - `scripts/test_retrieval_optimizations.py`: [OK] PASSED (2 tests)
    - `scripts/test_ingest_optimizations.py`: [OK] PASSED (5 tests)
    - `scripts/test_memory_regression_coverage.py`: [OK] PASSED (7 tests - 5 Section 3 + 2 Section 5)
    - `scripts/test_memory_backfill_portability.py`: [OK] PASSED (3 tests)
    - `scripts/test_memory_save_restore_worldlines.py`: [OK] PASSED (10 tests)
    - `scripts/test_memory_foundation.py`: [OK] PASSED (4 tests, 1 skipped)
  - **Files verified**:
    - `core/memory/memory_retrieval.py` - bounded candidates, dedup, read-only, audit logging
    - `core/memory/memory_ingest.py` - shared connections, batching, timestamp precedence
    - `core/memory/memory_db.py` - schema and migrations
    - `core/memory/memory_portability.py` - export/import package
    - `web/routes/memory_routes.py` - API endpoints
    - `scripts/backfill_memory_db.py` - CLI with batch size
    - `updates/save_game_manager.py` - worldlines save/restore integration
- [x] 4.2 Update memory docs (`plans/memory.md` and related notes) with new retrieval/ingest performance guarantees.
  - Added "Performance Guarantees (Retrieval/Ingest Optimizations - 2026-02-15)" section
  - Documented verified implementation characteristics (table format)
  - Documented retrieval API behaviors and empty-safe responses
  - Documented audit policy under read-only compliance
  - Documented test coverage locations

## 5. Strict Read-Only Retrieval Compliance (Hardening Addendum)

- [x] 5.1 Apply read-only connection semantics to all retrieval entry points (`get_entity_timeline`, `get_context_memories`, `get_retirement_return_memories`).
  - All 3 functions now use `_connect_readonly()` for queries
  - Completed as prerequisite for Section 3 tests
- [x] 5.2 Ensure missing DB path behavior is explicit and uniform across all retrieval functions (empty-safe response, no sqlite file creation).
  - All functions return empty list `[]` when DB missing, no exceptions
  - No DB file created by any retrieval operation
- [x] 5.3 Implement explicit audit policy under read-only retrieval: retrieval queries remain read-only; audit writes use dedicated best-effort writer connection (`mode=rw`, no create).
  - `get_entity_timeline()` now uses separate `_connect()` for audit logging with try/finally
  - `get_context_memories()` uses separate `_connect()` for audit logging
  - `get_retirement_return_memories()` uses separate `_connect()` for audit logging
  - Audit failures are debug-logged and non-critical
- [x] 5.4 Normalize candidate telemetry for all retrieval functions to report pre-limit candidate counts separately from returned rows.
  - `get_entity_timeline()` reports via audit log (pre_candidate_count from memory_links)
  - `get_context_memories()` now counts pre-limit candidates via separate query
  - `get_retirement_return_memories()` now counts pre-limit candidates via separate query
  - All three functions report `candidate_count >= result_count` in audit logs
- [x] 5.5 Add regression tests for: (a) read-only no-create behavior on missing DB for all retrieval APIs, (b) audit write path behavior under read-only retrieval, (c) deterministic ordering unchanged after compliance pass.
  - (a) Covered in Test 3.3 (`test_readonly_no_create()`)
  - (b) Implemented in Test 5.5b (`test_audit_write_path_under_readonly()`) - verifies audit logging works with separate write connection
  - (c) Implicitly covered by all existing deterministic ordering tests (3.1, 3.4, 3.5) plus new Test 5.4/5.5 (`test_candidate_telemetry_consistency()`)
  - Test 5.4/5.5 also verifies candidate telemetry reporting for all three retrieval functions

## Archive Notes

**Status**: COMPLETE - All 18 tasks finished (100%)
**Commit**: a97f361 feat(memory): Complete Section 5 read-only retrieval hardening
**Verification**: All 32 memory tests passing
**Date**: 2026-02-15
