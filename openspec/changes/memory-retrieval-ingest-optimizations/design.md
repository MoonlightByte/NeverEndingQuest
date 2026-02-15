## Context

Stage 1 memory foundation provides deterministic retrieval and idempotent ingest, but current implementation still carries avoidable costs and a few correctness gaps under larger datasets:

- Timeline retrieval can duplicate events when an entity has multiple links for one event.
- Retrieval scoring can process broader candidate sets than needed.
- Retrieval audit counters currently report returned rows instead of true pre-limit candidate population.
- Backfill/ingest paths reconnect repeatedly instead of reusing a single connection/transaction envelope.
- Backfilled history timestamps can use ingestion time instead of source chronology.

This design keeps schema disruption minimal and improves efficiency/correctness before any live LLM prompt integration.

## Goals / Non-Goals

**Goals:**
- Improve retrieval query efficiency while preserving deterministic rank behavior.
- Eliminate duplicate-event timeline rows for entity retrieval.
- Ensure retrieval telemetry reports true candidate-set statistics.
- Improve ingest throughput with shared connection and batched transactions.
- Preserve existing idempotency guarantees while improving timestamp fidelity.

**Non-Goals:**
- Live narrator/combat memory wiring.
- Vector index/embedding retrieval.
- Broad storage-engine replacement beyond sqlite.

## Decisions

1. **Two-stage retrieval query shape**
   - Decision: use bounded candidate pre-selection before final scoring/ranking.
   - Rationale: lowers work on large histories while preserving deterministic final ordering.
   - Alternative considered: keep single broad scoring query; rejected for scaling behavior.

2. **Event-level dedup in timeline retrieval**
   - Decision: collapse multi-link rows to one ranked row per event for timeline output.
   - Rationale: timeline consumers expect event semantics, not link multiplicity artifacts.
   - Alternative considered: expose duplicates and let caller dedup; rejected to keep API contracts clean.

3. **Read-only retrieval connection semantics**
   - Decision: open retrieval DB in read-only mode where applicable.
   - Rationale: avoid accidental DB creation and improve failure signal quality.
   - Alternative considered: continue default sqlite open; rejected due to silent create risk.

4. **Batch ingest execution model**
   - Decision: reuse one connection and transaction envelope per backfill run/source batch.
   - Rationale: significant overhead reduction versus per-entry reconnect.
   - Alternative considered: keep current per-entry convenience model; rejected for throughput costs.

5. **Timestamp precedence policy for backfill**
   - Decision: prefer source timestamp fields when available; use deterministic fallback only when source lacks timestamp.
   - Rationale: protects chronology-sensitive retrieval scoring and replay behavior.
   - Alternative considered: always use ingest-now; rejected due to chronology distortion.

6. **Split retrieval and audit connection responsibilities**
   - Decision: retrieval queries always use read-only connection; audit writes use separate best-effort writer connection (`mode=rw`, no create).
   - Rationale: preserves strict read-only retrieval semantics while retaining audit continuity when writable DB is available.
   - Alternative considered: disable audit in read-only mode; rejected to preserve telemetry continuity.

## Risks / Trade-offs

- [Query rewrite regressions] -> Add deterministic output tests and compare baseline ordering on fixture datasets.
- [Transaction scope too broad] -> Commit in controlled batch boundaries and keep malformed-entry tolerance behavior.
- [Timestamp parsing variability] -> Strict parsing + known fallback path with explicit normalization rules.
- [Read-only mode incompatibility on some paths] -> Keep explicit error handling and fallback only where required by tests.

## Migration Plan

1. Update retrieval SQL for bounded candidate pre-selection and event dedup.
2. Add retrieval telemetry corrections for pre-limit candidate counts.
3. Introduce/read-only retrieval connection mode and error handling.
4. Apply read-only retrieval semantics uniformly to all retrieval entry points and align missing-DB behavior.
5. Add explicit audit write policy via best-effort writer connection under read-only retrieval.
6. Refactor ingest/backfill path to shared connection and batched transactions.
7. Add/adjust tests for deterministic output, dedup, idempotency, timestamp fidelity, and read-only no-create guarantees.
8. Rollback plan: keep old query/ingest execution strategy behind reversible code path until tests pass.

## Open Questions

- Should candidate pre-selection limit be static or derived from requested limit (for example multiplier strategy)?
- Should timestamp normalization preserve timezone offsets verbatim or normalize to UTC at ingest time?
