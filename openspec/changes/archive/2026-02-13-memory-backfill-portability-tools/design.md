## Context

The memory foundation now supports full backfill from journal and conversation histories, plus dry-run/system-message controls. Operators now need finer control and portability support for campaign lifecycle operations.

This change keeps scope on tooling and contracts only. It does not alter narrator prompt wiring.

## Goals / Non-Goals

**Goals**
- Add source selection for backfill (`journal`, `conversation`, `combat`) via one explicit flag.
- Add export/import portability workflow with validation manifest.
- Preserve idempotent ingest behavior and non-destructive operation defaults.

**Non-Goals**
- Campaign archive UX implementation in web UI.
- Automatic archive scheduling.
- Any destructive overwrite behavior by default.

## Decisions

1. **Single source selector flag**
   - Use `--sources` CSV contract in `scripts/backfill_memory_db.py`.
   - Allowed values: `journal`, `conversation`, `combat`.
   - Invalid values fail fast with clear error message.

2. **Portability as explicit tool flow**
   - Add export/import helpers in script(s), not automatic startup hooks.
   - Export includes DB copy + JSON manifest (version, timestamp, source campaign metadata, row counts, hash).
   - Import validates manifest and schema compatibility before applying.

3. **Safe default behaviors**
   - Import defaults to non-destructive mode (fails if target DB exists unless override flag present).
   - `--dry-run` available for validation-only import path.

## Risks / Trade-offs

- [Operator misuse with wrong source selector] -> strict validation + explicit source summary output.
- [Schema drift across versions] -> manifest schema version and migration check before import.
- [Accidental overwrite] -> default no-overwrite behavior + explicit override flag.

## Migration Plan

1. Extend backfill script/parser for `--sources`.
2. Extend ingestion orchestrator with source-gating options.
3. Implement portability helpers:
   - export package
   - validate package
   - import package (safe mode)
4. Add tests and operator docs.
