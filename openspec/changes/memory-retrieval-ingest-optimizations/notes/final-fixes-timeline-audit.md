# Fix: Timeline Audit Connection Hardening

## Problem
`get_entity_timeline()` in `core/memory/memory_retrieval.py` logs audit entries using the **read-only** connection (`conn`), causing audit inserts to silently fail with `sqlite3.OperationalError` caught in `_log_retrieval_audit()`. This violates the Section 5.3 policy of "read-only query + separate best-effort writer for audit persistence".

## Current Code (Line 222-230)
```python
if enable_audit:
    _log_retrieval_audit(
        conn,  # BUG: This is the read-only connection!
        request_type="timeline",
        entity_scope={"entity_id": entity_id},
        rows=result,
        candidate_count=pre_candidate_count,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
```

## Required Fix
Change to match pattern used in `get_context_memories()` and `get_retirement_return_memories()`:

```python
if enable_audit and result:
    # Best-effort audit logging with separate write connection
    audit_conn = None
    try:
        audit_conn = _connect(db_path)
        _log_retrieval_audit(
            audit_conn,
            request_type="timeline",
            entity_scope={"entity_id": entity_id},
            rows=result,
            candidate_count=pre_candidate_count,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        audit_conn.commit()
    except Exception as audit_error:
        debug(f"MEMORY_RETRIEVAL: Audit logging failed (non-critical): {audit_error}", category="memory_retrieval")
    finally:
        if audit_conn is not None:
            audit_conn.close()
```

## Files to Modify
- `core/memory/memory_retrieval.py` (lines 222-230)

## Verification
After fix, update `test_audit_write_path_under_readonly()` in `scripts/test_memory_regression_coverage.py` to assert that audit rows ARE written (not just best-effort skipped):
```python
assert audit_count >= 1, f"Expected audit log entries after fix, got {audit_count}"
```

## Related
- Task 5.3 in `openspec/changes/memory-retrieval-ingest-optimizations/TASKS.md`
