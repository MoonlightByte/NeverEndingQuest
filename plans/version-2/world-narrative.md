# World Narrative Plan v0.3 (Copyright-First)

Status: Draft for review
Date: 2026-02-22
Owner: Narrative systems + memory integration

## Titan v2 Alignment Stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (schema and lifecycle updates not yet applied)
- Last tagged: 2026-02-26
- Retune focus: alignment relationship tables, Titan cycle logs, and world history proposal lifecycle

---

## 0) Priority Zero: Copyright Firewall

This is the top requirement for this plan.

Hard rules:
1. Raw uploads stay local only under `/user_uploads/text/` in project root (gitignored).
2. No direct source prose is allowed in any committable file.
3. No source-identifying metadata is allowed in committable JSON/DB outputs:
   - no title
   - no author
   - no series
   - no chapter names
   - no unique source labels
4. Anything that can reach GitHub (modules, memory exports, seeds, prompt packs) must be source-anonymous.
5. Fail closed: if scanner flags copyright risk, block commit/push.

Operational separation:
- Local Source Zone (gitignored): `/user_uploads/text/`
- Committable Derived Zone (repo-tracked): abstractions only, source-anonymous

---

## 1) What this plan solves

We want a rolling world narrative that:
1. Feels rich and coherent across long campaigns.
2. Reuses literary inspiration safely as abstract patterns.
3. Preserves Python as SRD 5e mechanical truth.
4. Integrates cleanly with current NeverEndingQuest hooks.

---

## 2) Core architecture contract

Non-negotiable rule:
- Python enforces mechanics; narrative layer influences pressure and continuity only.

Three-layer model:
1. Inspiration Layer (abstract motifs/archetypes/tone patterns only)
2. Canon Layer (campaign event truth)
3. Generation Layer (bounded retrieval for DM note/campaign/module builder)

If narrative guidance conflicts with mechanics, mechanics win.

---

## 3) Storage model

Decision:
- Extend `data/memory.db` for narrative state.
- Keep raw ingestion files in `/user_uploads/text/` only.
- Add a tracked baseline seed DB for tester installs: `data/world_narrative_seed.db`.

Why:
- Existing memory migration/retrieval/save portability already exists.
- Avoid duplicate persistence systems.
- Supports clean distribution: code + baseline narrative seed only.

No separate `narrative.db` for v1.

Runtime/bootstrap policy:
1. `data/world_narrative_seed.db` is the install baseline and is safe to commit (source-anonymous only).
2. Runtime working DB remains `data/memory.db` (gitignored) and may diverge per user/campaign.
3. First-run bootstrap: if `data/memory.db` is missing, copy from `data/world_narrative_seed.db`.
4. User uploads and local ingests never write back to seed DB.

---

## 4) Ingestion policy (strict)

Allowed to store in committable outputs:
- motif labels
- archetype labels
- faction dynamics
- thread templates
- tone vectors
- scene templates (abstract)

Never store in committable outputs:
- verbatim quotes
- long paraphrase near source wording
- title/author/series/source IDs linked to real books
- distinctive copyrighted character/place names from source novels

Local-only ingestion files in `/user_uploads/text/` may include source tracking for workflow support, but must remain gitignored.

---

## 5) Schema adjustments for copyright safety

This plan removes source bibliographic fields from committable DB design.

### 5.1 Committable inspiration tables (source-anonymous)

`inspiration_profiles`
- `profile_id TEXT PRIMARY KEY`
- `profile_kind TEXT NOT NULL` (`horror_gothic`, `heroic_epic`, `urban_intrigue`, etc.)
- `weights_json TEXT NOT NULL DEFAULT '{}'`
- `created_at TEXT NOT NULL`

`inspiration_atoms`
- `atom_id TEXT PRIMARY KEY`
- `profile_id TEXT NOT NULL`
- `atom_type TEXT NOT NULL` (`motif`, `archetype`, `relationship_pattern`, `faction_pattern`, `tone`, `arc_shape`, `scene_template`)
- `label TEXT NOT NULL`
- `description TEXT NOT NULL`
- `weight REAL NOT NULL DEFAULT 0.5`
- `srd_compatibility TEXT NOT NULL DEFAULT 'unknown'`
- `created_at TEXT NOT NULL`

Note:
- No `title`, `author`, `series`, or source bibliographic columns in committable DB.

### 5.2 Canon and generation tables (unchanged direction)

`narrative_threads`, `narrative_thread_events`, `narrative_actor_state`, `module_narrative_seeds`

These remain campaign-facing and contain no source references.

### 5.3 Cross-book atom convergence (how book 2 relates to book 1)

Goal:
- Build one shared inspiration graph, not isolated per-book silos.

Rules:
1. Atoms from each new book are merged by semantic identity (`atom_id`).
2. Repeated motifs/archetypes increase confidence/weight, not row count duplication.
3. New motifs/archetypes add coverage as new atom IDs.
4. No book identifiers are stored in committable rows.

Example:
- Book A exports `atom.liminal_threshold` and `atom.hidden_refuge`.
- Book B exports `atom.liminal_threshold` and `atom.masked_authority_predator`.
- Result: one shared `atom.liminal_threshold` (higher support/weight), plus one new atom (`atom.masked_authority_predator`).

Proposed relation tables:

`atom_relations`
- `relation_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `left_atom_id TEXT NOT NULL`
- `right_atom_id TEXT NOT NULL`
- `relation_type TEXT NOT NULL` (`co_occurs`, `tension`, `complements`, `escalates`)
- `weight REAL NOT NULL DEFAULT 0.5`
- `updated_at TEXT NOT NULL`
- `UNIQUE(left_atom_id, right_atom_id, relation_type)`

`atom_statistics`
- `atom_id TEXT PRIMARY KEY`
- `support_count INTEGER NOT NULL DEFAULT 0`
- `avg_weight REAL NOT NULL DEFAULT 0.5`
- `variance REAL NOT NULL DEFAULT 0.0`
- `updated_at TEXT NOT NULL`

Interpretation note:
- DB stores evidence/state only; it does not hardwire one canonical story.

### 5.4 Campaign-specific world model tables (interpreted layer)

`campaign_world_model`
- `campaign_id TEXT NOT NULL`
- `version INTEGER NOT NULL`
- `summary_json TEXT NOT NULL`
- `generated_by TEXT NOT NULL` (`ratio_llm`, `bootstrap_llm`)
- `created_at TEXT NOT NULL`
- `PRIMARY KEY(campaign_id, version)`

`campaign_world_delta`
- `delta_id INTEGER PRIMARY KEY AUTOINCREMENT`
- `campaign_id TEXT NOT NULL`
- `base_version INTEGER NOT NULL`
- `proposal_json TEXT NOT NULL`
- `applied INTEGER NOT NULL DEFAULT 0`
- `applied_at TEXT`
- `created_at TEXT NOT NULL`

Purpose:
- Enables similar but non-identical campaigns from the same 50+ book prior.

---

## 6) Extraction and analysis pipeline (Python)

Pipeline:
1. Read one source PDF locally from `/user_uploads/text/` (single-book mode only).
2. Run chunked extraction preprocessor to avoid context-window overflow:
   - script: `scripts/extract_book_pdf_for_ingestion.py`
   - output: local manifest + JSONL chunks under `/user_uploads/text/ingestion/`
   - chunk policy: bounded char/token budgets with overlap
3. Process chunks sequentially (map phase), never full-book prompt payloads.
4. Merge chunk-level abstractions into local ingestion JSON (reduce phase).
5. Validate schema + confidence.
6. Build source-anonymous atom export:
   - script: `scripts/build_source_anonymous_atoms.py`
   - input: local chunk JSONL
   - output: source-anonymous atoms + bounded builder prompt pack
7. Run copyright sanitizer:
   - remove source names
   - remove bibliographic references
   - remove high-overlap phrasing
8. Emit sanitized source-anonymous outputs to committable data paths.

Key principle:
- Two-stage output: local rich ingest -> sanitized anonymous export.
- One-book-at-a-time processing is mandatory to prevent model context freeze.

### 6.1 Toolkit upload entrypoint (player-facing)

Primary UI location:
- Module Toolkit Web GUI (`/toolkit`) with a new "World Narrative Sources" panel.

Upload contract:
1. Accept `pdf` only.
2. Save uploads under `/user_uploads/text/` only.
3. Enforce hard cutover: reject legacy `/user_uploads/` paths outside `/user_uploads/text/`.
4. Show copyright warning + explicit attestation before ingestion.
5. Run extraction and atom-build jobs asynchronously with progress/status.
6. Ingest only source-anonymous outputs into runtime DB.

API sketch:
- `POST /api/toolkit/world/sources/upload`
- `POST /api/toolkit/world/sources/extract`
- `POST /api/toolkit/world/sources/build-atoms`
- `POST /api/toolkit/world/sources/ingest`
- `GET /api/toolkit/world/jobs/<job_id>`

Safety:
- One active ingestion job per source file.
- File size/page/chunk caps enforced before processing.
- Fail closed on compliance or parsing errors.

---

## 7) Integration hooks (current codebase)

Canon event ingestion:
- `updates/plot_update.py` -> thread progression
- `core/ai/action_handler.py` -> transition/faction pressure events
- `core/managers/combat_manager.py` -> consequence events
- `core/managers/location_manager.py` -> location consequence transitions

Retrieval injection:
- `main.py` -> bounded `NARRATIVE PRESSURE` block in DM note path
- `core/managers/campaign_manager.py` -> cross-module continuity pack
- `core/generators/module_builder.py` -> continuity seed preamble
- `core/generators/module_stitcher.py` -> write back module narrative seeds

### 7.1 Character Sheet PDF mapping (deferred requirement)

Requirement for world-narrative build:
- Populate 5e sheet page 2 `Allies` (ALLIES & ORGANIZATIONS) from narrative continuity data.
- Do not use temporary/manual stopgap fields that will be replaced later.
- Source of truth should come from world-narrative outputs (relationship continuity + campaign world model), then map into PDF export.
- Keep existing page 2 mappings intact (`Feat+Traits`, `Backstory`, `Treasure`) while adding deterministic `Allies` population.

---

## 8) Retrieval contracts (bounded)

Turn-time pack:
- `get_narrative_turn_pack(module_name, location_id, active_entities, max_items=6)`
- output: `threats`, `obligations`, `continuity`

Transition pack:
- `get_transition_pressure_pack(from_module, to_module, max_items=6)`

Builder pack:
- `get_module_seed_pack(target_module, max_items=10)`

Ordering:
- priority desc -> recency desc -> stable id asc

### 8.1 World picture lifecycle (interpreted, not hardwired)

At campaign start:
1. Bootstrap LLM composes a `campaign_world_model` from:
   - merged global inspiration atoms
   - atom relations and statistics
   - selected module/campaign setup context
2. Result is a campaign-specific worldview snapshot (version 1).

During campaign play:
1. New canon events land in memory/thread tables.
2. Ratio LLM proposes worldview updates as `campaign_world_delta`.
3. Approved deltas are applied to create next `campaign_world_model` version.

Outcome:
- Campaigns remain family-similar (same inspiration prior) but relationship maps shift per playthrough.

### 8.2 LLM entry point contract #1 - EGO/Ratio drift and strategy

Role:
- Background coherence process for drift checks and strategic updates.

Inputs:
- Current `campaign_world_model` version
- Recent `memory_events` and `memory_links`
- Active `narrative_threads` and `narrative_actor_state`
- Recent narrator outputs (bounded window)

Outputs:
- Drift report (`aligned`, `soft_drift`, `hard_drift`)
- Proposed `campaign_world_delta`
- Optional updates for `narrative_actor_state` (allegiances, strategy posture)

Write permissions:
- May write interpreted narrative state (`campaign_world_delta`, actor strategy fields)
- May not write mechanical truth (HP/AC/slots/conditions/legal action outcomes)

### 8.3 LLM entry point contract #2 - Module Builder interpretation

Role:
- Uses world model to generate richer modules and feed continuity back.

Inputs:
- Latest `campaign_world_model`
- Active high-priority threads
- Actor-state pressures
- Existing module registry context

Outputs:
- Module narrative structure seeded from world pressures
- `module_narrative_seeds` additions
- Candidate thread continuations tied to new module content

Write permissions:
- May add narrative seeds and proposed thread continuations
- May not overwrite canonical event history

### 8.4 LLM entry point contract #3 - Narrator runtime interpretation

Role:
- Turn-by-turn storyteller that "discovers" the world via constrained context.

Inputs:
- Player inputs (highest live signal)
- Bounded pressure pack from world model + active threads
- DM note mechanical truth and SRD constraints

Outputs:
- Narrative response
- Action proposals for Python validators/handlers

Write permissions:
- Direct writes: none
- Indirect influence: emits events that Python systems convert into canonical state updates

### 8.5 Permission model summary

Facts vs interpretation split:
- Facts (append-only/audited): event history, mechanical outcomes, validated action results
- Interpretation (versioned/revisable): worldview summary, projected tensions, likely allegiances

Rule:
- Interpretation can be revised by Ratio.
- Facts cannot be silently rewritten.

---

## 9) Copyright compliance gates

### 9.1 Pre-commit gate
- Scan staged files for banned fields/terms:
  - `title`, `author`, `series`, `source_title`, `source_author`
  - source novel proper nouns list (maintained locally)
- Scan for suspicious overlap against local corpus hashes.
- Block commit on hit.

### 9.2 CI gate
- Repeat scanner in CI for pushed changes.
- Fail build on copyright risk.

### 9.3 Runtime publish gate
- Before writing module/memory artifacts intended for GitHub, run sanitizer.
- If sanitized output still risky, fail close and log.

### 9.4 Distribution gate (tester installs)
- GitHub/tester artifact set includes only:
  - Python/code changes
  - source-anonymous baseline `data/world_narrative_seed.db`
- Excludes always:
  - `/user_uploads/text/`
  - runtime `data/memory.db` and local ingest artifacts

---

## 10) Rollout plan

Phase 0 - Policy lock
- Approve copyright firewall + source-anonymous schema.
- Approve facts-vs-interpretation boundary and write-permission contracts.

Phase 1 - Foundation
- Add migration 003 for source-anonymous inspiration tables + narrative tables.
- Add `atom_relations`, `atom_statistics`, `campaign_world_model`, `campaign_world_delta`.
- Add `core/memory/narrative_state.py`.
- Add runtime bootstrap helper: seed DB -> `data/memory.db` when missing.

Phase 2 - Ingestion tooling
- Local ingestion scripts writing to `/user_uploads/text/`.
- Sanitized export pipeline to committable structures.
- Cross-book convergence job to update atom statistics/relations.
- Add toolkit upload endpoints and async job flow.

Phase 3 - World model bootstrap and Ratio loop
- Implement campaign-start world model bootstrap (`campaign_world_model` v1).
- Implement Ratio drift check loop and delta proposal/apply flow.

Phase 4 - Hook integration
- Wire plot/combat/transition hooks.
- Feed canonical events into thread and actor-state updates.

Phase 5 - Prompt and builder integration
- Inject pressure packs into DM note and module builder.
- Ensure narrator sees bounded interpreted world pressure, not raw DB dumps.

Phase 6 - Safety gates
- Pre-commit + CI + runtime publish blockers.

---

## 11) Verification checklist

Automated:
1. Migration idempotency.
2. Thread lifecycle correctness.
3. Retrieval ordering stability.
4. Save/export/import parity.
5. Copyright scan blocks any source identifiers.
6. Cross-book atom merge updates `support_count` and relation weights deterministically.
7. Ratio drift loop writes only interpreted state and never mechanical fields.
8. Seed bootstrap creates runtime DB correctly on fresh install.
9. Distribution checks confirm `/user_uploads/text/` and runtime DB are excluded from repo artifacts.

Manual:
1. Ingest one book locally under `/user_uploads/text/`.
2. Ingest second book and confirm shared atoms converge instead of duplicating.
3. Confirm exported atoms are source-anonymous.
4. Confirm DM/module outputs contain no title/author/source references.
5. Start two campaigns from same atom pool and verify world models are similar but not identical.
6. Confirm campaign continuity behavior still works across modules.
7. Use Toolkit upload panel end-to-end (upload -> extract -> atoms -> ingest) and verify no raw source leakage.

---

## 12) Review requests

Please review and confirm:
1. Source-anonymous requirement for all committable JSON/DB data.
2. Local-only ingestion files under `/user_uploads/text/`.
3. Banned metadata fields (`title`, `author`, etc.) in committable outputs.
4. Fail-closed commit/push gates as mandatory.
5. Cross-book atom convergence model (`atom_relations` + `atom_statistics`).
6. Campaign world model versioning (`campaign_world_model` + `campaign_world_delta`).
7. Three LLM entry-point contracts and write permissions.
8. Baseline seed DB distribution model and runtime bootstrap behavior.

If approved, next step is to implement Phase 1 and Phase 2 only.
