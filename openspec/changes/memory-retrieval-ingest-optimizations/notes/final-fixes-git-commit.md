# Fix: Git Commit Preparation

## Problem 1: Regression Test File Gitignored
`scripts/test_memory_regression_coverage.py` matches `.gitignore` pattern `test_*.py` and will not be committed by default.

## Solution
Option A (Recommended): Add explicit exception to `.gitignore`:
```gitignore
# Allow memory regression tests
!scripts/test_memory_regression_coverage.py
```

Option B: Force add in commit:
```bash
git add -f scripts/test_memory_regression_coverage.py
```

## Problem 2: OpenSpec Artifacts Untracked
The `openspec/changes/memory-retrieval-ingest-optimizations/` directory is untracked and won't be included in commit.

## Solution
Ensure all OpenSpec artifacts are added:
```bash
git add openspec/changes/memory-retrieval-ingest-optimizations/
```

## Files to Check Before Commit
```bash
# Check what's staged
git status

# Should show these ready to commit:
# - core/memory/memory_ingest.py
# - core/memory/memory_retrieval.py
# - plans/memory.md
# - scripts/backfill_memory_db.py
# - scripts/test_memory_regression_coverage.py (may need -f)
# - scripts/test_memory_foundation.py
# - updates/save_game_manager.py
# - openspec/changes/memory-retrieval-ingest-optimizations/
```

## Files to Verify Are ASCII-Clean
```bash
# Check for Unicode in Python files
grep -r '[^\x00-\x7F]' scripts/test_memory_regression_coverage.py core/memory/*.py
# Should return no matches
```

## Verification
After commit, verify:
```bash
git log --oneline -1
git show --stat HEAD
# All modified files + new test file + OpenSpec artifacts should be present
```
