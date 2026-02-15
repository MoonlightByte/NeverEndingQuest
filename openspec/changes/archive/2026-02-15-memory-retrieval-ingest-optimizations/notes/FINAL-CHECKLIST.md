# Final Implementation Checklist - Section 5 Hardening

## Overview
This document summarizes the remaining fixes needed before `memory-retrieval-ingest-optimizations` can be archived. All core functionality is implemented; these are final hardening and commit hygiene items.

## Critical Fixes Required

### Fix 1: Timeline Audit Connection (CRITICAL)
**File:** `core/memory/memory_retrieval.py` (lines 222-230)

**Problem:** `get_entity_timeline()` uses the read-only `conn` for audit logging, causing silent failures.

**Required Change:**
Replace current audit block with separate write connection pattern:
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

**Verification:** Update `test_audit_write_path_under_readonly()` to assert `audit_count >= 1` after fix.

---

### Fix 2: Git Commit Preparation

**File:** `.gitignore` OR commit command

**Problem:** `scripts/test_memory_regression_coverage.py` is ignored by `test_*.py` pattern.

**Option A (Recommended):**
Add to `.gitignore`:
```gitignore
# Allow memory regression tests
!scripts/test_memory_regression_coverage.py
```

**Option B:**
Force add during commit:
```bash
git add -f scripts/test_memory_regression_coverage.py
```

---

### Fix 3: OpenSpec Artifacts
**Files:** `openspec/changes/memory-retrieval-ingest-optimizations/`

**Action:** Ensure all artifacts are staged:
```bash
git add openspec/changes/memory-retrieval-ingest-optimizations/
```

---

## Files to Commit Summary

### Core Implementation (already modified)
- `core/memory/memory_retrieval.py` (needs Fix 1)
- `core/memory/memory_ingest.py` ✓
- `plans/memory.md` ✓
- `scripts/backfill_memory_db.py` ✓
- `scripts/test_memory_foundation.py` ✓
- `updates/save_game_manager.py` ✓

### Tests (need staging)
- `scripts/test_memory_regression_coverage.py` (needs Fix 2)

### Documentation (need staging)
- `openspec/changes/memory-retrieval-ingest-optimizations/` (needs Fix 3)

---

## Verification Steps

1. **Implement Fix 1:**
   ```bash
   python3 -m py_compile core/memory/memory_retrieval.py
   python3 scripts/test_memory_regression_coverage.py
   # All 7 tests should pass, audit test should show entries written
   ```

2. **ASCII Check:**
   ```bash
   grep -r '[^\x00-\x7F]' scripts/test_memory_regression_coverage.py
   # Should return nothing
   ```

3. **Stage and Commit:**
   ```bash
   git add -f scripts/test_memory_regression_coverage.py
   git add openspec/changes/memory-retrieval-ingest-optimizations/
   git status
   # Verify all files ready
   ```

4. **Archive Change:**
   ```bash
   /opsx-archive memory-retrieval-ingest-optimizations
   ```

---

## Success Criteria
- [ ] Timeline audit uses separate write connection
- [ ] All 7 regression tests pass with audit entries verified
- [ ] No Unicode in Python files
- [ ] All files staged for commit (including test file and OpenSpec)
- [ ] Change archived via OpenSpec workflow

## Dependencies
- Requires completion of Fix 1 before audit test can assert entries exist
- All other tasks are independent
