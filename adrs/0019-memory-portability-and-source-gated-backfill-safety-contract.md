# ADR-0019: Memory Portability and Source-Gated Backfill Safety Contract

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Campaign archive/restore workflows require safe memory transfer and controlled historical backfill.

## Decision
Provide explicit portability tooling and gated backfill:
- Export/validate/import memory packages with manifest and integrity checks.
- Non-destructive import defaults unless overwrite is explicit.
- Selective backfill sources (`journal`, `conversation`, `combat`) with fail-fast validation.

## Consequences
- Safer operations for migration, backup, and testing.
- Lower risk of accidental data loss.
- Added operational complexity in tooling, offset by deterministic contracts.

## Sources
- `AGENTS.md`
- `core/memory/memory_portability.py`
- `scripts/backfill_memory_db.py`
- `openspec/changes/archive/2026-02-13-memory-backfill-portability-tools/`
