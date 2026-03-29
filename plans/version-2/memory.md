# Memory Architecture Plan

Date: 2026-02-13
Project: NeverEndingQuest (Tabletop merge-safe branch)
Status: Planning in progress (schema + retrieval first)
Track reference: `plans/version-2/v2-narrative-track.md`

## Titan v2 Alignment Stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (Titan relationship retrieval requirements not yet folded in)
- Last tagged: 2026-02-26
- Retune focus: relationship-edge scoring, Titan provenance traces, and retrieval audit links

## Overview

This plan formalizes a two-layer memory system:

1. **God mode memory store**: complete historical record (high fidelity, append-first, low loss).
2. **Narrator retrieval lens**: strict, small, context-ranked memory packets for LLM prompts.

The core design is to keep history as complete as practical while preventing prompt bloat and retrieval noise.

Human memory inspiration (fragile + robust) is explicitly modeled:
- Day-to-day context fades.
- Identity, relationships, major events, and repeated patterns persist.
- Multiple retrieval pathways (social, procedural, episodic, sensory cue proxies) increase recall robustness.

### Conservative rollout note: narrator hygiene before DB retrieval

The current live narrator stack still relies primarily on file-backed conversation history, compression outputs, campaign summaries, and companion-memory packets. It does **not** yet use general bounded retrieval from `data/memory.db` during ordinary turn narration.

Because of that, prompt contamination must be handled in two phases:

1. **Prompt-plane hygiene first**: reduce off-location bleed by making live narrator payloads scene-first, leaner, and higher-signal.
2. **DB-backed retrieval second**: once the prompt plane is clean, add bounded `memory.db` retrieval packets only where they improve continuity without reintroducing noise.

This sequence matches the two-plane design:

- Plane A keeps near-complete historical truth.
- Plane B stays intentionally small and role-aware.

In practical terms, the live DM should behave like a current-scene commentator with a compact continuity packet, not a raw reader of every historical chronicle. Leaner narrator context is a feature here, not a regression, so long as identity, active plot pressure, recent turns, and mechanical truth remain visible.

Related current work:

- OpenSpec change `narrator-scene-context-hygiene-and-failclosed-ux` is the conservative first step.
- `memory.db` / world-narrative retrieval for live narration remains a follow-on change after prompt-plane hygiene is verified.

### Legacy companion-memory boundary after Phase 2A

The file-backed companion-memory runtime now carries the last planned live-stack tabletop extension for this path: additive per-PC relationship edges plus bounded active-PC-first prompt projection.

That means further work in this area SHOULD move into the version-2 architecture instead of continuing to deepen the legacy file-backed stack. In practical terms, the following belong to v2 from this point onward:

- relationship retrieval from `data/memory.db`,
- cross-scene or cross-module relationship ranking/scoring,
- Titan/provenance relationship analytics,
- and any broader replacement/unification of the companion-memory subsystem.

## Goals

1. Preserve long-term campaign continuity without overwhelming narrator prompts.
2. Keep stable identity across PC <-> NPC companion role transitions.
3. Promote active party relevance and major milestones over ambient noise.
4. Support retirement/return arcs as first-class retrievable memories.
5. Make retrieval deterministic, fast, and bounded for real-time play.

## Non-Negotiable Principles

1. Python state remains mechanical truth.
2. Memory DB is additive first, destructive never.
3. Identity is canonical; role is temporal.
4. Retrieval is token-budgeted by design.
5. Raw history completeness is allowed; narrator context is always filtered.

## Current Baseline

Audited baseline:

Existing sources already provide strong raw material:

- Conversation/context: `modules/conversation_history/conversation_history.json`, `core/ai/conversation_utils.py`
- Combat memory: `modules/conversation_history/combat_conversation_history.json`, `core/managers/combat_manager.py`
- Compression: `utils/compression/conversation_compressor_parallel.py`, `utils/compression/multi_pc_conversation_compressor.py`, `core/ai/chunked_compression.py`, `core/ai/cumulative_summary.py`
- Long-term summaries: `journal.json`, `modules/campaign_summaries/*.json`, `modules/campaign_archives/*`
- Companion memory systems: `core/memories/*`, `data/companion_memories/*`
- Role transitions/tabletop identity surfaces: `utils/pc_manager.py`, `web/routes/tabletop_party_routes.py`
- SQLite precedent: `core/managers/world_observer.py`, `data/world_surveillance.db`
- Continuity substrate (new): ingest/readiness continuity contract and gate outputs

## Continuity Substrate Update (Initial Build)

A module continuity baseline is now available and should be treated as pre-memory quality input:

1. Ingest emits `continuity_contract` metadata.
2. Sidecar audit validates continuity payload shape.
3. Readiness and bulk validators expose continuity gate outcomes.

For memory architecture planning, continuity outcomes should be used as:
- ingestion quality signals,
- module readiness prerequisites,
- and candidate ranking hints for future narrative-thread synthesis.

This layer is not a memory event source by itself; it is metadata that improves trust in upstream narrative structure.

## Next Milestone

Integrate continuity gate outcomes into memory ingestion/retrieval quality signals so narrative retrieval can prefer continuity-healthy module context.

## Exit Criteria

- Memory retrieval contracts can consume continuity quality metadata deterministically.
- Continuity quality does not override mechanical truth or write boundaries.
- Retrieval remains bounded and token-safe with continuity-aware ranking.

## Locked Build Order

1. Schema and migrations
2. Retrieval contracts and scoring
3. Journal ingestion and compilation
4. Narrative integration hooks

Do not invert this order.

---

## Retrieval-Centric Architecture

### Two Planes

**Plane A: Historical Plane (God mode)**
- Stores near-complete records.
- Optimized for fidelity, traceability, and replay.
- Can grow large safely.

**Plane B: Prompt Plane (Narrator lens)**
- Returns small top-K sets only.
- Optimized for relevance, recency, and role-context fit.
- Hard token and item caps.

Implementation note:
- Before any wider `memory.db` integration, the prompt plane should first exclude high-noise historical surfaces already available in file-backed runtime payloads (for example, stacked historical location chronicles or remote-location atlas dumps). Clean prompt assembly comes before richer retrieval.

This separation prevents "million factoid" failure while preserving full campaign history.

### Memory Robustness Model

Each memory event carries structured recall signals:

- `persistence_class`: how durable the memory should be.
- `modality_tags`: retrieval pathways (episodic/social/procedural/sensory-symbolic/plot).
- `reinforcement_count`: how often memory was revisited/reconfirmed.
- `decay_profile`: expected fade speed for rank scoring.
- `pinned`: hard-retain events.
- `priority_active_pc`: active-party relevance flag.

Result: robust memories stay retrievable even as ambient history grows.

---

## Canonical Schema (Stage 1 + Retrieval Extensions)

Database target: `data/memory.db`

### 1) `entities`
Canonical identity objects.

Columns:
- `entity_id TEXT PRIMARY KEY`
- `display_name TEXT NOT NULL`
- `entity_kind TEXT NOT NULL`  -- character, faction, location, item, event, other
- `is_retired INTEGER NOT NULL DEFAULT 0`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `metadata_json TEXT`

Indexes:
- `idx_entities_kind_name(entity_kind, display_name)`

### 2) `entity_aliases`
Name drift support.

Columns:
- `alias_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `entity_id TEXT NOT NULL` FK
- `alias_name TEXT NOT NULL`
- `alias_type TEXT NOT NULL DEFAULT 'name'`
- `source TEXT NOT NULL DEFAULT 'system'`
- `created_at TEXT NOT NULL`

Constraints:
- `UNIQUE(entity_id, alias_name)`

### 3) `entity_roles`
Temporal role transitions.

Columns:
- `role_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `entity_id TEXT NOT NULL` FK
- `role TEXT NOT NULL`  -- player, npc_companion, npc_world, retired_lord, retired_lady, other
- `start_ts TEXT NOT NULL`
- `end_ts TEXT`
- `source TEXT NOT NULL DEFAULT 'system'`
- `reason TEXT`

Indexes:
- `idx_roles_active(entity_id, end_ts)`
- `idx_roles_timeline(entity_id, start_ts DESC)`

### 4) `journal_entries`
Idempotent ingested source units.

Columns:
- `entry_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `entry_ts TEXT NOT NULL`
- `title TEXT`
- `content TEXT NOT NULL`
- `source_type TEXT NOT NULL`  -- journal, campaign_summary, combat_summary, imported, manual
- `source_ref TEXT`
- `checksum TEXT NOT NULL`
- `metadata_json TEXT`
- `created_at TEXT NOT NULL`

Constraints:
- `UNIQUE(source_type, checksum)`

### 5) `memory_events`
Primary retrieval unit.

Columns:
- `event_id TEXT PRIMARY KEY`
- `entry_id INTEGER` FK -> journal_entries.entry_id
- `event_ts TEXT NOT NULL`
- `event_type TEXT NOT NULL`  -- relationship, milestone, combat, role_transition, travel, dialogue, quest, rest, item, other
- `summary TEXT NOT NULL`
- `detail_json TEXT`
- `importance INTEGER NOT NULL DEFAULT 50`  -- 0..100
- `persistence_class TEXT NOT NULL DEFAULT 'ambient'`
  - Allowed: `identity_core`, `campaign_major`, `relationship_core`, `procedural`, `ambient`
- `decay_profile TEXT NOT NULL DEFAULT 'medium'`
  - Allowed: `none`, `slow`, `medium`, `fast`
- `modality_tags_json TEXT NOT NULL DEFAULT '[]'`
  - Examples: `['episodic','social','procedural','sensory_symbolic','plot_state']`
- `reinforcement_count INTEGER NOT NULL DEFAULT 0`
- `last_reinforced_ts TEXT`
- `priority_active_pc INTEGER NOT NULL DEFAULT 0`
- `pinned INTEGER NOT NULL DEFAULT 0`
- `created_at TEXT NOT NULL`

Indexes:
- `idx_events_ts(event_ts DESC)`
- `idx_events_priority(pinned DESC, priority_active_pc DESC, importance DESC, event_ts DESC)`
- `idx_events_persistence(persistence_class, decay_profile, event_ts DESC)`

### 6) `memory_links`
Event <-> entity graph.

Columns:
- `link_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `event_id TEXT NOT NULL` FK -> memory_events.event_id
- `entity_id TEXT NOT NULL` FK -> entities.entity_id
- `link_role TEXT NOT NULL`  -- actor, target, witness, owner, counterpart
- `link_salience REAL NOT NULL DEFAULT 0.5`
- `metadata_json TEXT`

Constraints:
- `UNIQUE(event_id, entity_id, link_role)`

Indexes:
- `idx_links_entity(entity_id, link_role)`
- `idx_links_event(event_id)`

### 7) `companion_memory_state`
Compatibility bridge for companion affect state.

Columns:
- `entity_id TEXT PRIMARY KEY` FK -> entities.entity_id
- `state_json TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### 8) Optional `retrieval_snippets`
Precompiled prompt-ready snippets.

Columns:
- `snippet_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `entity_id TEXT` FK
- `event_id TEXT` FK
- `scene_type TEXT NOT NULL`  -- combat, social, travel, rest, planning, recap
- `snippet_text TEXT NOT NULL`
- `score REAL NOT NULL DEFAULT 0.5`
- `created_at TEXT NOT NULL`

Indexes:
- `idx_snippets_lookup(entity_id, scene_type, score DESC)`

---

## Retrieval Contracts (Schema-First)

### Required Stage 1 functions

- `init_memory_db(db_path: str) -> None`
- `run_memory_migrations(db_path: str) -> None`
- `ingest_journal_entry(entry: Dict[str, Any]) -> Dict[str, Any]`
- `create_memory_event(event: Dict[str, Any]) -> str`
- `create_memory_link(link: Dict[str, Any]) -> int`
- `get_entity_timeline(entity_id: str, limit: int = 25) -> List[Dict[str, Any]]`

### Retrieval expansion planned immediately after Stage 1

- `get_context_memories(scene_type: str, active_entities: List[str], limit: int = 12) -> List[Dict[str, Any]]`
- `get_relationship_memories(entity_a: str, entity_b: str, limit: int = 15) -> List[Dict[str, Any]]`
- `get_retirement_return_memories(entity_id: str, limit: int = 20) -> List[Dict[str, Any]]`

### Minimal HTTP route (inspection/test)

- `GET /api/memory/entity/<entity_id>?limit=25`

---

## Retrieval Ranking Design

### Weighted score (deterministic)

For each candidate memory event:

`score = Wp + Wa + Wi + Wr + Wm + Wd + Wc`

Where:
- `Wp`: pinned boost
- `Wa`: active-PC relevance boost
- `Wi`: normalized importance boost
- `Wr`: reinforcement boost (`log1p(reinforcement_count)`)
- `Wm`: modality/scene match boost
- `Wd`: decay-adjusted recency term
- `Wc`: class weight (`identity_core` > `campaign_major` > `relationship_core` > `procedural` > `ambient`)

### Default weight profile (initial)

- `pinned`: +100
- `active_pc`: +25
- `importance`: `importance * 0.35`
- `reinforcement`: `ln(1 + reinforcement_count) * 6`
- `modality_match`: +10 (scene-aligned tags), +4 (partial)
- `persistence_class`: identity_core +30, campaign_major +24, relationship_core +20, procedural +14, ambient +4
- `decay/recency`: 0 to +20 based on profile and age

### Decay behavior

- `none`: no decay
- `slow`: half-life 90 days
- `medium`: half-life 30 days
- `fast`: half-life 7 days

Pseudocode:
- `recency = exp(-ln(2) * age_days / half_life_days)`
- `Wd = recency * 20`

### Retrieval guardrails

1. Never return more than configured `limit`.
2. Enforce per-prompt token cap independently of item count.
3. Guarantee diversity by class and modality (avoid all-combat or all-recent packs).
4. Always include at least one identity_core or campaign_major item when available.

---

## SQL Query Drafts (Implementation-Ready)

These drafts are designed for SQLite and can be used directly in `memory_retrieval.py` with parameter binding.

### Query A: Candidate Pool for `get_entity_timeline`

Purpose:
- Pull a bounded candidate set quickly.
- Keep scoring stable even when historical table grows.

```sql
WITH candidate_events AS (
    SELECT
        me.event_id,
        me.event_ts,
        me.event_type,
        me.summary,
        me.importance,
        me.persistence_class,
        me.decay_profile,
        me.modality_tags_json,
        me.reinforcement_count,
        me.last_reinforced_ts,
        me.priority_active_pc,
        me.pinned,
        ml.link_role,
        CAST((julianday('now') - julianday(me.event_ts)) AS REAL) AS age_days
    FROM memory_events me
    JOIN memory_links ml ON ml.event_id = me.event_id
    WHERE ml.entity_id = :entity_id
)
SELECT *
FROM candidate_events
ORDER BY
    pinned DESC,
    priority_active_pc DESC,
    importance DESC,
    event_ts DESC
LIMIT :candidate_limit;
```

Recommended defaults:
- `candidate_limit = max(limit * 8, 120)`

### Query B: SQL-Only Ranked Timeline (No math extensions required)

Purpose:
- Fully deterministic ranking in SQL only.
- Uses bucketed decay to avoid `exp()` dependency.

```sql
WITH candidate_events AS (
    SELECT
        me.event_id,
        me.event_ts,
        me.event_type,
        me.summary,
        me.importance,
        me.persistence_class,
        me.decay_profile,
        me.modality_tags_json,
        me.reinforcement_count,
        me.priority_active_pc,
        me.pinned,
        ml.link_role,
        CAST((julianday('now') - julianday(me.event_ts)) AS REAL) AS age_days
    FROM memory_events me
    JOIN memory_links ml ON ml.event_id = me.event_id
    WHERE ml.entity_id = :entity_id
),
scored AS (
    SELECT
        ce.*,
        (
            CASE WHEN ce.pinned = 1 THEN 100 ELSE 0 END +
            CASE WHEN ce.priority_active_pc = 1 THEN 25 ELSE 0 END +
            (ce.importance * 0.35) +
            CASE ce.persistence_class
                WHEN 'identity_core' THEN 30
                WHEN 'campaign_major' THEN 24
                WHEN 'relationship_core' THEN 20
                WHEN 'procedural' THEN 14
                ELSE 4
            END +
            CASE
                WHEN ce.decay_profile = 'none' THEN 20
                WHEN ce.decay_profile = 'slow' THEN
                    CASE
                        WHEN ce.age_days <= 30 THEN 20
                        WHEN ce.age_days <= 90 THEN 16
                        WHEN ce.age_days <= 180 THEN 12
                        WHEN ce.age_days <= 365 THEN 8
                        ELSE 4
                    END
                WHEN ce.decay_profile = 'medium' THEN
                    CASE
                        WHEN ce.age_days <= 7 THEN 20
                        WHEN ce.age_days <= 30 THEN 14
                        WHEN ce.age_days <= 90 THEN 8
                        WHEN ce.age_days <= 180 THEN 4
                        ELSE 1
                    END
                ELSE
                    CASE
                        WHEN ce.age_days <= 3 THEN 20
                        WHEN ce.age_days <= 7 THEN 10
                        WHEN ce.age_days <= 30 THEN 4
                        ELSE 1
                    END
            END +
            MIN(18, ce.reinforcement_count * 2)
        ) AS retrieval_score
    FROM candidate_events ce
)
SELECT
    event_id,
    event_ts,
    event_type,
    summary,
    priority_active_pc,
    pinned,
    link_role,
    retrieval_score
FROM scored
ORDER BY retrieval_score DESC, event_ts DESC
LIMIT :limit;
```

### Query C: Scene-Aware Context Pack (`get_context_memories`)

Purpose:
- Retrieve top memories for current scene using modality match and active entities.

Input parameters:
- `:scene_type` in `combat|social|travel|rest|planning|recap`
- dynamic active entity list via CTE `active_entities`

```sql
WITH active_entities(entity_id) AS (
    VALUES
    -- populate dynamically in Python: (?),(?),(?)
    (:active_entity_1)
),
candidate AS (
    SELECT DISTINCT
        me.event_id,
        me.event_ts,
        me.event_type,
        me.summary,
        me.persistence_class,
        me.priority_active_pc,
        me.pinned,
        me.modality_tags_json,
        CAST((julianday('now') - julianday(me.event_ts)) AS REAL) AS age_days
    FROM memory_events me
    JOIN memory_links ml ON ml.event_id = me.event_id
    JOIN active_entities ae ON ae.entity_id = ml.entity_id
),
scored AS (
    SELECT
        c.*,
        (
            CASE WHEN c.pinned = 1 THEN 100 ELSE 0 END +
            CASE WHEN c.priority_active_pc = 1 THEN 25 ELSE 0 END +
            CASE c.persistence_class
                WHEN 'identity_core' THEN 30
                WHEN 'campaign_major' THEN 24
                WHEN 'relationship_core' THEN 20
                WHEN 'procedural' THEN 14
                ELSE 4
            END +
            CASE
                WHEN :scene_type = 'combat' AND EXISTS (
                    SELECT 1 FROM json_each(c.modality_tags_json)
                    WHERE value IN ('procedural','episodic')
                ) THEN 10
                WHEN :scene_type = 'social' AND EXISTS (
                    SELECT 1 FROM json_each(c.modality_tags_json)
                    WHERE value IN ('social','relationship')
                ) THEN 10
                WHEN :scene_type IN ('travel','rest','planning') AND EXISTS (
                    SELECT 1 FROM json_each(c.modality_tags_json)
                    WHERE value IN ('plot_state','episodic','sensory_symbolic')
                ) THEN 10
                ELSE 0
            END
        ) AS retrieval_score
    FROM candidate c
)
SELECT
    event_id,
    event_ts,
    event_type,
    summary,
    retrieval_score
FROM scored
ORDER BY retrieval_score DESC, event_ts DESC
LIMIT :limit;
```

### Query D: Relationship Memory Query

Purpose:
- Pull shared memory line between two entities.

```sql
SELECT
    me.event_id,
    me.event_ts,
    me.event_type,
    me.summary,
    me.importance,
    me.persistence_class,
    me.priority_active_pc,
    me.pinned
FROM memory_events me
WHERE EXISTS (
    SELECT 1
    FROM memory_links mla
    WHERE mla.event_id = me.event_id
      AND mla.entity_id = :entity_a
)
AND EXISTS (
    SELECT 1
    FROM memory_links mlb
    WHERE mlb.event_id = me.event_id
      AND mlb.entity_id = :entity_b
)
ORDER BY
    me.pinned DESC,
    me.importance DESC,
    me.event_ts DESC
LIMIT :limit;
```

### Query E: Retirement/Return Timeline Query

Purpose:
- Retrieve role-transition milestones for an entity.

```sql
SELECT
    me.event_id,
    me.event_ts,
    me.event_type,
    me.summary,
    me.pinned,
    me.importance
FROM memory_events me
JOIN memory_links ml ON ml.event_id = me.event_id
WHERE ml.entity_id = :entity_id
  AND me.event_type IN ('role_transition', 'milestone')
  AND (
      me.summary LIKE '%retire%'
      OR me.summary LIKE '%return%'
      OR me.persistence_class IN ('identity_core', 'campaign_major')
  )
ORDER BY me.pinned DESC, me.importance DESC, me.event_ts DESC
LIMIT :limit;
```

### Implementation note: SQL-only vs Hybrid scoring

Preferred rollout path:
- Stage 1: SQL-only scoring (Query B) for deterministic baseline.
- Stage 2: Hybrid scoring (SQL candidate pool + Python post-score) if we need more nuanced decay/reinforcement math.

Both approaches keep retrieval bounded and fast.

---

## Python Binding Examples (sqlite3)

These examples are intentionally minimal and match the named-parameter SQL style above.

### Example 1: `get_entity_timeline`

```python
import sqlite3
from typing import Any, Dict, List


def get_entity_timeline(conn: sqlite3.Connection, entity_id: str, limit: int = 25) -> List[Dict[str, Any]]:
    sql = """
    WITH candidate_events AS (
        SELECT
            me.event_id,
            me.event_ts,
            me.event_type,
            me.summary,
            me.importance,
            me.persistence_class,
            me.decay_profile,
            me.modality_tags_json,
            me.reinforcement_count,
            me.priority_active_pc,
            me.pinned,
            ml.link_role,
            CAST((julianday('now') - julianday(me.event_ts)) AS REAL) AS age_days
        FROM memory_events me
        JOIN memory_links ml ON ml.event_id = me.event_id
        WHERE ml.entity_id = :entity_id
    ),
    scored AS (
        SELECT
            ce.*,
            (
                CASE WHEN ce.pinned = 1 THEN 100 ELSE 0 END +
                CASE WHEN ce.priority_active_pc = 1 THEN 25 ELSE 0 END +
                (ce.importance * 0.35) +
                CASE ce.persistence_class
                    WHEN 'identity_core' THEN 30
                    WHEN 'campaign_major' THEN 24
                    WHEN 'relationship_core' THEN 20
                    WHEN 'procedural' THEN 14
                    ELSE 4
                END +
                CASE
                    WHEN ce.decay_profile = 'none' THEN 20
                    WHEN ce.decay_profile = 'slow' THEN
                        CASE
                            WHEN ce.age_days <= 30 THEN 20
                            WHEN ce.age_days <= 90 THEN 16
                            WHEN ce.age_days <= 180 THEN 12
                            WHEN ce.age_days <= 365 THEN 8
                            ELSE 4
                        END
                    WHEN ce.decay_profile = 'medium' THEN
                        CASE
                            WHEN ce.age_days <= 7 THEN 20
                            WHEN ce.age_days <= 30 THEN 14
                            WHEN ce.age_days <= 90 THEN 8
                            WHEN ce.age_days <= 180 THEN 4
                            ELSE 1
                        END
                    ELSE
                        CASE
                            WHEN ce.age_days <= 3 THEN 20
                            WHEN ce.age_days <= 7 THEN 10
                            WHEN ce.age_days <= 30 THEN 4
                            ELSE 1
                        END
                END +
                MIN(18, ce.reinforcement_count * 2)
            ) AS retrieval_score
        FROM candidate_events ce
    )
    SELECT
        event_id,
        event_ts,
        event_type,
        summary,
        priority_active_pc,
        pinned,
        link_role,
        retrieval_score
    FROM scored
    ORDER BY retrieval_score DESC, event_ts DESC
    LIMIT :limit;
    """

    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, {"entity_id": entity_id, "limit": limit}).fetchall()
    return [dict(r) for r in rows]
```

### Example 2: Dynamic active-entity binding for scene retrieval

```python
def build_active_entities_cte(active_entities: List[str]) -> str:
    placeholders = ", ".join(["(?)" for _ in active_entities])
    return f"WITH active_entities(entity_id) AS (VALUES {placeholders})"


def get_context_memories(conn: sqlite3.Connection, scene_type: str, active_entities: List[str], limit: int = 12):
    if not active_entities:
        return []

    cte = build_active_entities_cte(active_entities)
    sql = f"""
    {cte},
    candidate AS (
        SELECT DISTINCT
            me.event_id,
            me.event_ts,
            me.event_type,
            me.summary,
            me.persistence_class,
            me.priority_active_pc,
            me.pinned,
            me.modality_tags_json
        FROM memory_events me
        JOIN memory_links ml ON ml.event_id = me.event_id
        JOIN active_entities ae ON ae.entity_id = ml.entity_id
    )
    SELECT event_id, event_ts, event_type, summary
    FROM candidate
    ORDER BY pinned DESC, priority_active_pc DESC, event_ts DESC
    LIMIT ?;
    """

    params = [*active_entities, limit]
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]
```

### Example 3: Safe transaction pattern for ingestion

```python
def ingest_entry(conn: sqlite3.Connection, payload: Dict[str, Any]) -> int:
    sql = """
    INSERT INTO journal_entries (
        entry_ts, title, content, source_type, source_ref, checksum, metadata_json, created_at
    ) VALUES (
        :entry_ts, :title, :content, :source_type, :source_ref, :checksum, :metadata_json, :created_at
    )
    ON CONFLICT(source_type, checksum) DO NOTHING;
    """
    with conn:
        conn.execute(sql, payload)
        row = conn.execute(
            "SELECT entry_id FROM journal_entries WHERE source_type = :source_type AND checksum = :checksum",
            {"source_type": payload["source_type"], "checksum": payload["checksum"]},
        ).fetchone()
        return int(row[0])
```

---

## Test Matrix (Minimal, Deterministic)

Use this matrix as the first retrieval validation suite before narrative integration.

### Fixture setup

Create one entity `acheron` and insert six events linked to it:

1. `identity_core`, pinned=1, old timestamp
2. `campaign_major`, pinned=0, medium recency
3. `relationship_core`, active_pc=1, recent
4. `procedural`, active_pc=1, very recent, reinforcement=4
5. `ambient`, active_pc=0, very recent
6. `campaign_major`, active_pc=1, old but reinforced

### Expected order checks

1. Pinned identity event ranks above non-pinned ambient event even when older.
2. Active-PC relationship/procedural events outrank equally recent ambient events.
3. Reinforced older campaign-major can outrank unreinforced medium-importance recent ambient.
4. With `limit=3`, results are stable across repeated calls (deterministic ordering).

### Scene-type checks (`get_context_memories`)

1. `scene_type='combat'` returns at least one procedural/episodic-tagged memory in top results when available.
2. `scene_type='social'` favors relationship/social-tagged memories.
3. Empty `active_entities` returns empty list (no broad table scan fallback).

### Role-transition checks

1. Insert retirement and return events for same entity.
2. `get_retirement_return_memories` returns both in descending rank/time.
3. Entity identity remains constant (`entity_id` unchanged) across role transitions.

### Idempotency checks

1. Ingest same journal payload twice with identical checksum.
2. Verify one `journal_entries` row only.
3. Verify retrieval output unchanged after second ingest.

---

## God Mode vs Prompt Mode (Operational Policy)

### God mode retention policy

- Keep ingested `journal_entries` and linked `memory_events` as complete as feasible.
- Avoid destructive deletion; prefer soft archival or low-priority classification.
- Maintain checksums to avoid duplicate ingest bloat.

### Prompt mode policy

- Use top-K only (default 8-20 items depending on scene).
- Build scene packs:
  - combat: procedural + recent threat milestones + party bond markers
  - social: relationship_core + identity_core + unresolved commitments
  - travel/rest: campaign_major + pending quest + return/retirement hooks

Result: complete history exists, narrator receives only actionable memory.

---

## Scale and Performance Expectations

### Practical campaign growth estimate (1 year, weekly)

Expected ranges:
- Curated/high-signal extraction: 5k-20k `memory_events`
- Medium extraction density: 20k-80k `memory_events`

Estimated SQLite footprint:
- 5k-20k events: roughly 20-150 MB
- 20k-80k events: roughly 150-600 MB

These sizes are acceptable for local SQLite with indexes.

### Query performance target

- Top-K retrieval under 10-30 ms local for indexed queries at target scale.
- Ingestion can be slower; retrieval must stay fast.

### Bloat controls

1. Idempotent checksum ingest.
2. Optional low-value event consolidation jobs.
3. Optional precomputed `retrieval_snippets` for hot paths.
4. Periodic `VACUUM` and index maintenance (non-blocking maintenance window).

### Performance Guarantees (Retrieval/Ingest Optimizations - 2026-02-15)

**Verified Implementation Characteristics:**

| Capability | Implementation | Guarantee |
|------------|---------------|-----------|
| **Bounded Candidate Pre-selection** | `get_entity_timeline()` uses `MIN(MAX_LIMIT, safe_limit * 3)` candidate pool | Query cost O(candidate_limit), not O(table_size) |
| **Event-level De-duplication** | `SELECT DISTINCT` in final projection + subquery-based entity filtering | One row per event even with multiple entity links |
| **Deterministic Ordering** | Score DESC → event_ts DESC → event_id ASC tie-breaker | Identical results across repeated calls |
| **Read-Only Retrieval** | All retrieval APIs use `_connect_readonly()` with existence check | No implicit DB creation, empty-safe on missing DB |
| **Shared Connection Ingest** | Optional `conn` parameter in `ingest_journal_entry()` | Single connection per batch, no per-entry overhead |
| **Batched Transactions** | `ingest_journal_entries_batch()` with configurable `batch_size` | Throughput scaling with bounded memory per batch |
| **Timestamp Precedence** | `entry_ts > timestamp > source_ts > created_at > now()` | Deterministic temporal ordering regardless of source |
| **Idempotent Ingest** | `ON CONFLICT(source_type, checksum) DO NOTHING` | Safe re-ingestion without duplicate creation |

**Retrieval API Behaviors:**

- `get_entity_timeline(entity_id, limit=25)` → List of events ranked by composite score
  - Returns `[]` (empty list) when DB missing or entity not found
  - Never creates DB file on read-only connection
  - Candidate telemetry reported in audit log when `enable_audit=True`

- `get_context_memories(scene_type, active_entities, limit=12)` → Scene-aware memory pack
  - Modality tag matching for scene-type relevance boost
  - Returns `[]` when DB missing or no active entities

- `get_retirement_return_memories(entity_id, limit=20)` → Role transition milestones
  - Filters for `event_type IN ('role_transition', 'milestone')` with retirement/return keywords
  - Returns `[]` when DB missing or no matching events

**Audit Policy (Read-Only Compliance):**

- Retrieval queries use read-only connections exclusively
- Audit writes (when enabled) use separate best-effort writer connections
- Audit failures are debug-logged and non-blocking
- No retrieval latency impact from audit persistence

**Test Coverage:**

- 5 regression tests in `scripts/test_memory_regression_coverage.py`
  - Deterministic ordering with de-duplication (3.1)
  - Batch-mode idempotency (3.2)
  - Read-only no-create behavior (3.3)
  - Deterministic tie-breaker (3.4)
  - Context memories determinism (3.5)

---

## Priority Semantics (Active PCs and Major Events)

Set or boost `priority_active_pc` when:
- Event links current `active_character`.
- Event links any `partyMembers` in `party_tracker.json`.
- Event is role transition, retirement, or return.
- Event changes module/world state materially.

Force retention candidates (`pinned = 1` policy candidates):
- Party identity transitions.
- Irreversible campaign consequences.
- Core relationship pivots (bond, betrayal, oath, rescue, death).
- Keep governance milestones and return triggers.

---

## Migration and Compatibility Strategy

### Phase A: Foundation
- Add DB + migration table + schema.
- No prompt integration yet.

### Phase B: Retrieval introduction
- Implement `get_entity_timeline` with ranking.
- Add minimal API route for inspection.

### Phase C: Ingestion bridge
- Import `journal.json` idempotently.
- Optionally ingest summaries/combat artifacts.

### Phase D: Narrative integration
- Inject bounded context packs only.
- Keep existing compression behavior intact during transition.

Compatibility rule:
- Existing JSON flows continue to function if DB is unavailable.

Operational fallback notes:
- If DB initialization fails, startup continues and memory retrieval endpoints return empty safe responses.
- If migration fails mid-session, gameplay paths remain on JSON/compression memory without hard-stop behavior.
- Ingest failures are partial-tolerant: malformed entries are logged and skipped while valid entries continue.
- Retrieval audit logging is best-effort and does not block retrieval if audit tables are missing.

---

## Acceptance Criteria (Schema + Retrieval First)

1. Migrations are idempotent.
2. Journal ingest deduplicates on checksum.
3. `get_entity_timeline` returns deterministic ranked results.
4. Ranking reflects persistence class, modality match, active-PC priority, and decay.
5. Retirement/return events are retrievable for known entities.
6. Prompt-mode retrieval remains bounded by item and token caps.

---

## EGO/RATIO Readiness Delta (Future-Compatible by Design)

This section defines low-risk schema and service hooks that keep the memory system compatible with a future EGO/RATIO background-control architecture without committing to that build now.

### Intent

If EGO/RATIO is adopted later, memory retrieval should already support:
- auditable decisions,
- policy-driven tuning,
- safe canary/shadow evaluation,
- rollback-friendly control changes,
- and clear fact-vs-inference separation.

### Additive schema extensions (planned)

#### 1) `memory_policy_profiles`
Versioned retrieval policy bundles (weights, caps, decay knobs).

Columns:
- `policy_id TEXT PRIMARY KEY`
- `name TEXT NOT NULL`
- `version INTEGER NOT NULL`
- `scope TEXT NOT NULL`  -- global, scene, mode
- `policy_json TEXT NOT NULL`  -- scoring weights, scene caps, diversity rules
- `is_active INTEGER NOT NULL DEFAULT 0`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `created_by TEXT NOT NULL DEFAULT 'system'`

#### 2) `memory_policy_assignments`
Maps policy profiles to runtime contexts.

Columns:
- `assignment_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `context_key TEXT NOT NULL`  -- e.g. combat, social, recap, multiplayer
- `policy_id TEXT NOT NULL` FK -> memory_policy_profiles.policy_id
- `effective_from_ts TEXT NOT NULL`
- `effective_to_ts TEXT`

#### 3) `retrieval_audit_log`
Captures retrieval inputs/outputs and score traces.

Columns:
- `audit_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `request_ts TEXT NOT NULL`
- `request_type TEXT NOT NULL`  -- timeline, scene_pack, relationship
- `scene_type TEXT`
- `entity_scope_json TEXT NOT NULL`
- `policy_id TEXT`
- `candidate_count INTEGER NOT NULL`
- `result_count INTEGER NOT NULL`
- `result_event_ids_json TEXT NOT NULL`
- `score_breakdown_json TEXT NOT NULL`  -- per-event components
- `token_estimate INTEGER NOT NULL DEFAULT 0`
- `latency_ms INTEGER NOT NULL DEFAULT 0`
- `mode TEXT NOT NULL DEFAULT 'live'`  -- live, shadow, replay

Indexes:
- `idx_retrieval_audit_ts(request_ts DESC)`
- `idx_retrieval_audit_type(request_type, request_ts DESC)`

#### 4) `controller_change_log`
Future EGO/RATIO or human policy edits with rollback metadata.

Columns:
- `change_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `change_ts TEXT NOT NULL`
- `actor TEXT NOT NULL`  -- human, ego, ratio, system
- `target_type TEXT NOT NULL`  -- policy, threshold, prompt_knob
- `target_key TEXT NOT NULL`
- `old_value_json TEXT`
- `new_value_json TEXT NOT NULL`
- `reason TEXT`
- `rollback_of_change_id INTEGER`

#### 5) `memory_event_provenance` (optional but recommended)
Separates hard facts from inferred narrative synthesis.

Columns:
- `event_id TEXT PRIMARY KEY` FK -> memory_events.event_id
- `source_kind TEXT NOT NULL`  -- journal, summary, combat_log, inferred
- `source_ref TEXT`
- `confidence REAL NOT NULL DEFAULT 1.0`
- `verification_state TEXT NOT NULL DEFAULT 'unverified'`  -- verified, unverified, disputed
- `last_verified_ts TEXT`

### Service contracts to reserve now

These do not need implementation in Stage 1, but names and signatures should be reserved:

- `get_memory_policy(context_key: str) -> Dict[str, Any]`
- `set_memory_policy(context_key: str, policy: Dict[str, Any], actor: str, reason: str) -> str`
- `log_retrieval_audit(audit_payload: Dict[str, Any]) -> int`
- `run_shadow_retrieval(query_payload: Dict[str, Any], policy_id: str) -> Dict[str, Any]`
- `compare_retrieval_runs(baseline_run_id: int, candidate_run_id: int) -> Dict[str, Any]`

### Operational guardrails for future controller integration

1. **Read-first activation**: EGO/RATIO starts by observing retrieval logs only.
2. **Write budget**: cap policy changes per session/day.
3. **Cooldowns**: no rapid oscillation between policy profiles.
4. **Canary-first**: candidate policy must pass shadow evaluation before live use.
5. **Rollback path**: all policy changes must be reversible via `controller_change_log`.

### Backward-compatibility stance

- These are additive tables and optional hooks.
- Core Stage 1 memory retrieval remains fully functional without EGO/RATIO features enabled.
- No dependency on world observer placeholders is required.

### Definition of done for "EGO-ready foundation"

1. Retrieval scoring can be expressed via external policy JSON (even if static initially).
2. Retrieval calls can emit structured audit logs with score component traces.
3. Live retrieval can run with fixed default policy if advanced control layers are absent.

---

## Immediate Next Step (Before OpenSpec Launch)

Implement Stage 1 skeleton with full retrieval-aware schema:

1. Create DB bootstrap + migrations.
2. Create ingestion stubs with checksum dedupe.
3. Implement `get_entity_timeline` scoring query.
4. Add one test route for inspection output.

After review and your approval, we can convert this directly into OpenSpec artifacts and execute implementation tasks.

---

## Operator Workflow Examples (Backfill + Portability)

### Selective backfill

Run only journal source:

```bash
python3 scripts/backfill_memory_db.py --sources journal
```

Run journal + combat only with safe preview:

```bash
python3 scripts/backfill_memory_db.py --sources journal,combat --dry-run
```

Include system messages in source set:

```bash
python3 scripts/backfill_memory_db.py --sources conversation,combat --include-system --dry-run
```

### Portability export/import

Export package (DB copy + manifest):

```bash
python3 scripts/backfill_memory_db.py --export-package exports/campaign_memory_pkg
```

Validate import compatibility without writing:

```bash
python3 scripts/backfill_memory_db.py --import-package exports/campaign_memory_pkg --db-path data/memory.db --dry-run
```

Import package into target DB (safe default blocks overwrite):

```bash
python3 scripts/backfill_memory_db.py --import-package exports/campaign_memory_pkg --db-path data/memory.db
```

Force replace existing target DB only when intentional:

```bash
python3 scripts/backfill_memory_db.py --import-package exports/campaign_memory_pkg --db-path data/memory.db --overwrite
```

### Manifest expectations

Export manifest should include:
- schema version (`memory-db-package/v1`)
- export timestamp
- DB filename and SHA-256 integrity hash
- row-count summary for key tables
- applied migration IDs

---

## Many Worlds Save/Restore Support (2026-02-15)

### Snapshot-Isolated Memory DB

Memory DB state is now part of the save/restore contract, ensuring timeline coherence when players reload earlier saves.

**Behavior:**

1. **Save creates memory package:** Each save game includes a `memory_db_package/` directory containing a snapshot of `data/memory.db` at that point in time.

2. **Restore imports memory package:** When restoring a save, the memory DB is rewound to the saved state, preventing timeline drift where gameplay JSON rewinds but memory DB stays "in the future."

3. **Legacy saves use deterministic fallback:** Saves created before memory parity was implemented trigger a clean memory DB initialization (not "keep current state"), ensuring consistent behavior.

### Worldline Lineage Metadata

Each save includes lineage fields that track timeline ancestry:

```json
{
  "save_id": "uuid-of-this-save",
  "worldline_id": "uuid-of-timeline",
  "lineage": {
    "parent_save_id": "uuid-of-parent-save-or-null",
    "parent_worldline_id": "uuid-of-parent-worldline-or-null",
    "fork_origin_save_id": "uuid-of-fork-origin-or-null",
    "created_after_restore": true
  },
  "memory_package": {
    "status": "success",
    "row_counts": {...}
  }
}
```

### Fork-on-First-Save-After-Restore

Default worldline behavior:

1. After any restore operation, the next save creates a new `worldline_id` (divergent branch).
2. Subsequent saves (without another restore) continue on the same worldline.
3. Process restart preserves fork intent via `modules/conversation_history/restore_context.json`.

**Example timeline:**

```
Save A (worldline W1) -> Play -> Save B (worldline W1)
Restore A -> Play -> Save C (worldline W2, forked from A)
Save D (worldline W2, continues on fork)
Restore C -> Play -> Save E (worldline W3, forked from C)
```

### Integration Points

- `updates/save_game_manager.py`: Save/restore hooks for memory package export/import
- `modules/conversation_history/restore_context.json`: Persisted fork context for process-restart safety
- `core/memory/memory_portability.py`: Package validation and transport primitives

### Listing Saves with Lineage

Save listing (`SaveGameManager.list_save_games()`) includes:
- `memory_package_present`: boolean indicating if memory package exists
- All lineage fields from metadata

This enables UI/CLI visualization of branch structure without loading individual saves.
- basic campaign metadata snapshot
