## Implementation Notes for Next Agent

**Current State:** Section 5.1-5.5 implementation is 95% complete. Three final fixes required before archive.

### Completed (Do Not Modify)
- ✅ All retrieval functions use `_connect_readonly()` for queries
- ✅ All retrieval functions return empty list for missing DB
- ✅ Context and retirement functions use separate audit connections
- ✅ Candidate telemetry implemented for all three functions
- ✅ Section 5 regression tests added
- ✅ Test tearDown cleanup fixed

### Remaining Fixes (CRITICAL)

#### Fix 1: Timeline Audit Connection (HIGH PRIORITY)
**Location:** `core/memory/memory_retrieval.py:222-230`

The timeline function still uses the read-only connection for audit logging. This is the only function not following the Section 5.3 policy.

**Pattern to Match:** Look at `get_context_memories()` lines ~334-353 or `get_retirement_return_memories()` lines ~424-442 for the correct implementation.

**Quick Fix:**
```python
# Replace lines 222-230 with:
if enable_audit and result:
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

**Then:** Update `test_audit_write_path_under_readonly()` to assert `audit_count >= 1`.

---

#### Fix 2: Gitignore Test File Exception
**Location:** `.gitignore`

Add near end of file:
```gitignore
# Memory regression tests (not auto-generated)
!scripts/test_memory_regression_coverage.py
```

---

#### Fix 3: Stage OpenSpec Artifacts
**Command:**
```bash
git add openspec/changes/memory-retrieval-ingest-optimizations/
```

---

### Verification After Fixes
```bash
# 1. Syntax check
python3 -m py_compile core/memory/memory_retrieval.py

# 2. Run all memory tests
python3 scripts/test_memory_regression_coverage.py
# Should show: "Audit log written: X entries" (not "skipped")

# 3. Check git status
git status
# Should show test file and OpenSpec ready to commit

# 4. Archive
/opsx-archive memory-retrieval-ingest-optimizations
```

### Success Criteria
- [ ] Timeline audit uses separate write connection with try/finally
- [ ] Audit test asserts entries exist (not just best-effort)
- [ ] `.gitignore` has exception for regression test
- [ ] OpenSpec artifacts staged
- [ ] All 7 regression tests pass
- [ ] Change archived
