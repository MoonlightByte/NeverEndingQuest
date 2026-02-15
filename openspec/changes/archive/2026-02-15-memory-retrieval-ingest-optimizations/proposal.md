## Why

The memory foundation is functional, but retrieval and ingest paths still have avoidable inefficiencies and edge-case correctness gaps (duplicate timeline rows, broad candidate scoring, per-entry reconnect overhead, and audit counters that report post-limit counts). Hardening these now keeps memory DB a clean, reliable substrate before any live LLM memory integration.

## What Changes

- Optimize retrieval queries with bounded candidate pre-selection and deterministic de-duplication by event.
- Correct retrieval audit metrics so candidate counts reflect true pre-limit populations.
- Harden read-only retrieval connection behavior to avoid accidental DB creation on missing paths.
- Apply strict read-only behavior consistently across all retrieval entry points, not only timeline retrieval.
- Make audit behavior explicit under read-only retrieval by using a dedicated best-effort writer path.
- Optimize backfill/ingest execution to use shared connections and batched transactions for throughput.
- Improve ingest timestamp fidelity so backfilled events preserve meaningful source chronology when available.
- Non-goals:
  - No narrator/combat prompt integration in this change.
  - No speculative semantic-rerank/vector stack.
  - No schema-breaking changes to gameplay JSON.
- Rollout risk and fallback:
  - Risk: query-plan regressions on large datasets.
  - Fallback: keep SQL behind deterministic tests and preserve legacy-safe limits until validated.
  - Maintain additive behavior and SP/MP compatibility.

## Capabilities

### New Capabilities
- `memory-retrieval-query-efficiency`: retrieval performs bounded candidate selection and event-level de-duplication while preserving deterministic ordering.
- `memory-ingest-batch-efficiency`: ingest/backfill supports shared connection and batched transaction execution without weakening idempotency.

### Modified Capabilities
- `memory-retrieval-ranking`: ranking/audit requirements now include accurate pre-limit candidate telemetry and read-only retrieval safety.
- `memory-ingestion-idempotency`: idempotency requirements are extended to batch-mode ingest and timestamp normalization rules.

## Impact

- Affected code:
  - `core/memory/memory_retrieval.py`
  - `core/memory/memory_ingest.py`
  - `scripts/backfill_memory_db.py`
  - tests under `scripts/test_memory_*`
- Data/storage:
  - No required schema break; optional additive indexes/helpers only
- APIs/contracts:
  - Retrieval semantics stay deterministic with tighter performance/correctness guarantees
  - Backfill behavior remains idempotent with stronger throughput guarantees
- Compatibility:
  - Additive and backward-compatible with existing memory DB files
  - No gameplay mode behavior change until future LLM integration work
