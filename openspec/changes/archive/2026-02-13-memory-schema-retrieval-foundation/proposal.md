## Why

NeverEndingQuest currently stores memory across multiple JSON artifacts and compression outputs, which works for short continuity but makes deterministic long-term retrieval, role-transition continuity, and milestone recall increasingly fragile as campaigns grow. We need a canonical memory foundation now so narrative context stays high-signal and token-bounded while preserving complete historical records for future systems.

## What Changes

- Introduce a new SQLite-backed memory foundation with additive, migration-safe schema for entities, role history, journal entries, memory events, and event links.
- Implement deterministic retrieval contracts focused on high-signal context packs (`get_entity_timeline` first) with explicit scoring factors (pinned, active-PC, persistence class, decay, reinforcement, modality match).
- Add idempotent ingestion contracts for journal-derived memory records (checksum-based dedupe).
- Define explicit "God mode history" vs "prompt mode retrieval" behavior to preserve near-complete history while strictly bounding narrator input.
- Add retirement/return and PC<->NPC role-transition memory semantics as first-class retrieval targets.
- Include additive readiness hooks for possible future EGO/RATIO controller integration (policy profiles, retrieval audit logs, controller change logs), without enabling controller behavior in this change.

## Capabilities

### New Capabilities
- `memory-foundation-schema`: Canonical memory schema, migrations, and compatibility guarantees for long-term memory persistence.
- `memory-retrieval-ranking`: Deterministic retrieval contracts and ranking behavior for timeline and context-pack memory queries.
- `memory-ingestion-idempotency`: Checksum-based ingest behavior for journal and summary sources with duplicate-safe imports.
- `memory-role-transition-continuity`: Stable identity and temporal role semantics for PC/NPC transitions plus retirement/return retrieval.
- `memory-observability-readiness`: Retrieval audit and policy-surface readiness hooks for future controller experiments.

### Modified Capabilities
- None.

## Impact

- Affected code:
  - New modules under `core/memory/` (schema/migration, retrieval, ingest scaffolding)
  - Optional inspect/test routes under `web/routes/` (read-only retrieval endpoint)
  - Optional startup ingest hook in `main.py` or adjacent startup path (guarded, non-blocking)
- Data/storage:
  - New local SQLite database target `data/memory.db`
  - Existing JSON assets remain operational and compatible during rollout
- APIs/contracts:
  - Service contracts: `init_memory_db`, `run_memory_migrations`, `ingest_journal_entry`, `create_memory_event`, `create_memory_link`, `get_entity_timeline`
  - Optional inspection route: `GET /api/memory/entity/<entity_id>?limit=25`
- Dependencies:
  - Uses Python stdlib `sqlite3`; no external DB service required
- Merge safety and SP/MP impact:
  - Additive-only integration; no upstream feature removal
  - Runtime behavior remains backward compatible for single-player and tabletop modes
  - TABLETOP-specific host edits, if any, remain minimal and marked with `# TABLETOP MODE:` comments
- Risk/fallback:
  - If DB unavailable, retrieval paths fall back to existing JSON/compression behavior
  - Idempotent ingest and bounded retrieval reduce bloat and prompt regression risk
