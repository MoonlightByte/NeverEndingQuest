# ADR-0017: Deterministic Memory Retrieval and Idempotent Ingest

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Non-deterministic retrieval and duplicate ingest reduce trust and make regressions hard to diagnose.

## Decision
Use deterministic scoring/tie-break retrieval and checksum-based idempotent ingestion.

## Consequences
- Reproducible retrieval outputs for tests and audits.
- Safe repeated backfills without duplicate event growth.
- Requires maintenance of ranking factors as schema evolves.

## Sources
- `AGENTS.md`
- `core/memory/memory_retrieval.py`
- `core/memory/memory_ingest.py`
