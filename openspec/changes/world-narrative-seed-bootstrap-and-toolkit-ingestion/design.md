## Context

This change formalizes Phase 1/2 for world-narrative ingestion under strict copyright-firewall rules already decided by product policy.

The system goal is not to hardwire story from DB rows. Instead, this phase builds safe infrastructure so later interpretation layers (EGO/Ratio, Module Builder, Narrator) can consume interpreted world model snapshots.

## Goals / Non-Goals

**Goals:**
- Implement seed bootstrap and migration support for world-model tables.
- Implement fail-closed source-anonymous atom ingestion.
- Implement toolkit upload/extract/build/ingest APIs with one-active-job lock.
- Implement minimal toolkit UI panel to drive the workflow safely.

**Non-Goals:**
- Build full interpreted world-model retrieval integration in this change.
- Build multi-file queue orchestration beyond one active ingestion job.
- Add EPUB handling.

## Architecture Decisions

1. **Runtime DB bootstrap policy (MUST)**
   - Runtime source of truth remains `data/memory.db`.
   - If runtime DB is missing and seed exists, copy `data/world_narrative_seed.db` -> `data/memory.db` once.
   - Never mutate seed DB from runtime ingest paths.

2. **Schema migration scope (MUST)**
   - Additive only. No destructive migration.
   - Add/ensure tables: `atom_relations`, `atom_statistics`, `campaign_world_model`, `campaign_world_delta`.

3. **Source-anonymous ingest gate (MUST)**
   - Ingest accepts only atom payloads that pass banned-key and banned-term scanning.
   - Compliance failures are hard errors for ingest operation.

4. **Toolkit job model (MUST)**
   - One active ingestion job globally (simple lock) for this phase.
   - Endpoints expose status by `job_id`.
   - Upload path is constrained to `/user_uploads/text/`.

5. **UI contract (SHOULD)**
   - Add one new tab/panel in toolkit for world narrative sources.
   - Keep panel minimal and operational, not stylistically large.

6. **Meta-source layering rubric (MUST + SHOULD)**
   - Use `meta_source_rubric.md` as the contract for profile taxonomy, atom-type targets, and influence governance.
   - Use `profile_assignment_list.md` as the initial ingest queue for meta priors before fantasy batches.
   - Treat strategy/cosmology/horror sources as meta priors and fantasy novels as specificity priors.
   - Keep campaign runtime behavior sourced from interpreted world model snapshots.

## Risks / Trade-offs

- **Risk:** Runtime bootstrap copy could hide seed drift.
  - **Mitigation:** log explicit bootstrap status and source path.
- **Risk:** Job lock can feel restrictive.
  - **Mitigation:** explicit 409 response with active job metadata.
- **Risk:** Compliance false positives block ingest.
  - **Mitigation:** return detailed hit paths/terms for operator correction.

## Migration Plan

1. Add seed-bootstrap helper and world-model migration in `core/memory/memory_db.py`.
2. Export helper in `core/memory/__init__.py`.
3. Add `core/memory/world_narrative_ingest.py` validation + upsert flow.
4. Add `web/routes/world_narrative_routes.py` endpoints.
5. Register routes in `web/web_interface.py` and apply bootstrap at startup.
6. Add toolkit panel + JS flow in `web/templates/module_toolkit.html`.
7. Add tests and run compile + route/service smoke checks.

Rollback:
- Keep additive schema.
- Disable route registration and panel wiring.
- Keep bootstrap helper inert if not called.

## Verification Strategy

- Compile:
  - `python3 -m py_compile core/memory/memory_db.py core/memory/world_narrative_ingest.py web/routes/world_narrative_routes.py web/web_interface.py`
- Service tests:
  - compliance gate pass/fail
  - seed bootstrap success/skip/error paths
- Route tests:
  - upload path enforcement
  - one-job lock behavior
  - ingest fail-closed on compliance hits
- Manual smoke:
  - Toolkit upload -> extract -> build-atoms -> ingest -> job-status
