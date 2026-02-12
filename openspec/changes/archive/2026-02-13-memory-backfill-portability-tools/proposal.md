## Why

The Stage 1 memory foundation is implemented, but two operator workflows remain manual or implicit:

1. Selective backfill by source channel (journal vs conversation vs combat) is not yet exposed.
2. Campaign memory DB portability (export/import validation + restore flow) is not yet formalized.

These two capabilities are important for future campaign archiving and restore workflows, and capturing them in OpenSpec preserves implementation history for future maintainers.

## What Changes

- Add source-selection controls to backfill tooling (`--sources`) so operators can run targeted imports.
- Add DB portability tooling contracts for export/import preparation, including manifest metadata and validation checks.
- Define non-destructive restore behavior and compatibility checks for campaign continuation workflows.
- Add test coverage and docs for operator-safe usage.

## Capabilities

### New Capabilities
- `memory-backfill-source-selection`: selective source import controls for memory backfill tooling.
- `memory-db-portability`: export/import workflow support for campaign memory DB handoff and reload.

### Modified Capabilities
- `memory-ingestion-idempotency`: expanded to support selective source execution without changing dedupe guarantees.

## Impact

- Affected code:
  - `scripts/backfill_memory_db.py` (source selector flags)
  - `core/memory/memory_ingest.py` (source gating)
  - new utility module(s) under `core/memory/` or `scripts/` for portability manifest/validation
- Data/storage:
  - existing `data/memory.db` remains canonical
  - optional portable artifact output (DB + manifest metadata)
- APIs/contracts:
  - backfill invocation contract extended with explicit source selection
  - portability contract introduces export/import validation steps
- Compatibility:
  - additive-only change
  - no impact to gameplay if tooling is not invoked
