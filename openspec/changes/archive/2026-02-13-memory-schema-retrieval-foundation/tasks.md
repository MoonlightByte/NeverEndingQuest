## 1. Memory DB Foundation

- [x] 1.1 Create `core/memory/` package scaffold with `memory_db.py`, `memory_retrieval.py`, `memory_ingest.py`, and package exports in `core/memory/__init__.py`.
- [x] 1.2 Implement migration bootstrap in `core/memory/memory_db.py` with idempotent schema creation for entities, aliases, roles, journal entries, memory events, memory links, and companion state.
- [x] 1.3 Add retrieval-readiness optional tables (`memory_policy_profiles`, `memory_policy_assignments`, `retrieval_audit_log`, `controller_change_log`, optional `memory_event_provenance`) guarded as additive, non-required paths.
- [x] 1.4 Verify schema bootstrap compiles and runs twice without changes (idempotency smoke check using local temp DB).

## 2. Retrieval Contracts and Ranking

- [x] 2.1 Implement `get_entity_timeline(entity_id, limit)` in `core/memory/memory_retrieval.py` using deterministic SQL ranking (pinned, active-PC, importance, persistence class, decay bucket, reinforcement).
- [x] 2.2 Implement scene-aware retrieval helper contract (`get_context_memories`) with bounded top-K and safe empty-entity behavior.
- [x] 2.3 Implement retirement/return retrieval helper contract (`get_retirement_return_memories`) with deterministic ordering.
- [x] 2.4 Add retrieval guardrails (limit bounds, deterministic tie-break, result shaping) and optional audit-log emission hook that is no-op when disabled.
- [x] 2.5 Verify retrieval determinism and ranking behavior by running `python3 scripts/test_memory_retrieval_plan.py`.

## 3. Idempotent Ingestion Bridge

- [x] 3.1 Implement `ingest_journal_entry` in `core/memory/memory_ingest.py` using source/checksum dedupe and transaction-safe writes.
- [x] 3.2 Add batch ingest helper for `journal.json` with malformed-entry tolerance (continue on error with structured logging).
- [x] 3.3 Implement deferred-link behavior for low-confidence entity extraction (store entry even if links are skipped).
- [x] 3.4 Verify idempotency by ingesting same payload twice and asserting single persisted entry.

## 4. Integration Surface (Read-Only First)

- [x] 4.1 Add a minimal read-only inspection route `GET /api/memory/entity/<entity_id>?limit=25` in `web/routes/` with graceful fallback if DB unavailable.
- [x] 4.2 Wire route registration with merge-safe minimal host changes and `# TABLETOP MODE:` annotations only where host file hooks are required.
- [x] 4.3 Add optional startup initialization hook for memory DB bootstrap in a guarded path that does not block existing gameplay startup.
- [x] 4.4 Verify route smoke behavior for success and fallback modes.

## 5. Validation, Safety, and Documentation

- [x] 5.1 Add/refresh tests for schema migration idempotency, retrieval ordering, retirement/return query coverage, and ingest dedupe.
- [x] 5.2 Run syntax validation: `python3 -m py_compile core/memory/memory_db.py core/memory/memory_retrieval.py core/memory/memory_ingest.py`.
- [x] 5.3 Run memory retrieval matrix tests: `python3 scripts/test_memory_retrieval_plan.py`.
- [x] 5.4 Document fallback behavior and operational notes in `plans/memory.md` and any new module docstrings, keeping ASCII-only user-facing log text.
