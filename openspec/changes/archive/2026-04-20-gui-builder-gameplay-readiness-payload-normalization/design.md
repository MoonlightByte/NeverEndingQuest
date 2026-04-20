# Design: GUI Builder Gameplay Readiness Payload Normalization

## Context
`scripts/audit_module_gameplay.py` emits JSON nested under `target`. `scripts/audit_module_readiness.py` currently reads several gameplay fields as if they are top-level. That mismatch preserves gameplay exit-code failure but loses structured `monster_media_findings`, causing inaccurate readiness and publishability reporting.

## Goals
- Normalize gameplay payload access in a deterministic, testable way.
- Preserve gameplay audit semantics.
- Make readiness and publishability reflect structured monster-media debt accurately.

## Non-Goals
- Broad gameplay audit redesign.
- Finisher outcome semantics work.
- Toolkit UI ordering work.
- LLM-assisted ambiguity handling.

## Decisions

### Decision: Readiness SHALL normalize gameplay payload access
Readiness SHALL use a bounded normalization path that tolerates the current nested `target` shape and, if easy, compatible top-level access.

### Decision: Structured media debt SHALL propagate accurately
Fix-list generation, toolkit media policy summaries, and publishability passthrough SHALL use normalized gameplay findings so counts and slugs remain accurate.

### Decision: Scope SHALL remain deterministic and local
The fix SHALL stay limited to readiness/publishability consumers and SHALL NOT widen into unrelated semantics changes.

## Architecture
- Add a small normalization helper or equivalent bounded access path in `scripts/audit_module_readiness.py`.
- Use normalized gameplay data in:
  - `evaluate_gameplay_gate(...)`
  - `_build_fix_list(...)`
  - toolkit media policy summary construction
- Preserve publishability passthrough while ensuring it receives corrected readiness output.

## Risks / Trade-offs
- Over-fitting to one payload shape could break compatibility; tolerant normalization is preferred if simple.
- Too much helper extraction could be more churn than the bug warrants; keep the fix small and readable.

## Migration Plan
1. Normalize gameplay payload access in readiness.
2. Propagate corrected structured media debt summaries.
3. Add targeted regression coverage.
4. Verify against the known contradiction case.

## Verification Plan
- `python3 -m py_compile scripts/audit_module_readiness.py scripts/audit_module_publishability.py`
- Run targeted readiness/publishability tests.
- Show one concrete before/after example where structural media debt count and slugs are now accurate.
