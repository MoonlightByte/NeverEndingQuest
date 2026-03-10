## 0. Meta-source governance rubric

- [ ] 0.1 Maintain `meta_source_rubric.md` in this change with MUST/SHOULD contracts for meta vs fantasy prior layering.
- [ ] 0.2 Align ingestion profile naming and validation expectations to the rubric before implementation handoff.
- [ ] 0.3 Maintain `profile_assignment_list.md` and keep Wave A meta-prior assignment order explicit.

## 1. Seed bootstrap and migration foundation

- [ ] 1.1 Add/verify `DEFAULT_WORLD_NARRATIVE_SEED_DB_PATH` and `bootstrap_memory_db_from_seed(...)` in `core/memory/memory_db.py`.
- [ ] 1.2 Ensure additive migration coverage for `atom_relations`, `atom_statistics`, `campaign_world_model`, `campaign_world_delta` in `core/memory/memory_db.py`.
- [ ] 1.3 Export bootstrap helper in `core/memory/__init__.py`.
- [ ] 1.4 Verify idempotency: initialize/migrate DB twice without errors.

## 2. Source-anonymous ingest service

- [ ] 2.1 Create `core/memory/world_narrative_ingest.py` with banned-key and banned-term validation helpers.
- [ ] 2.2 Implement fail-closed `validate_source_anonymous_payload(...)` contract.
- [ ] 2.3 Implement `ingest_source_anonymous_atoms(...)` upsert/update logic for profiles/atoms/statistics.
- [ ] 2.4 Ensure ingest never writes source identifiers or raw source text fields.

## 3. Toolkit API routes and job lock

- [ ] 3.1 Create `web/routes/world_narrative_routes.py` with endpoints:
  - `POST /api/toolkit/world/sources/upload`
  - `POST /api/toolkit/world/sources/extract`
  - `POST /api/toolkit/world/sources/build-atoms`
  - `POST /api/toolkit/world/sources/ingest`
  - `GET /api/toolkit/world/jobs/<job_id>`
- [ ] 3.2 Enforce `/user_uploads/text/` path constraints and `pdf`-only upload policy.
- [ ] 3.2a Reject legacy `/user_uploads/` paths outside `/user_uploads/text/` (hard cutover, no transition mode).
- [ ] 3.3 Enforce one-active-job lock with deterministic 409 response when locked.
- [ ] 3.4 Add route registration in `web/web_interface.py` and keep host edits merge-safe.

## 4. Toolkit UI panel wiring

- [ ] 4.1 Add a World Narrative Sources panel in `web/templates/module_toolkit.html`.
- [ ] 4.2 Add mandatory copyright attestation checkbox and local-only warning text.
- [ ] 4.3 Add JS handlers for upload/extract/build/ingest/status polling with safe error rendering.

## 5. Startup bootstrap integration

- [ ] 5.1 In `web/web_interface.py`, call seed bootstrap before `init_memory_db`.
- [ ] 5.2 Log bootstrap status (`success`, `runtime_exists`, `seed_missing`, `error`) without blocking startup.

## 6. Tests and verification

- [ ] 6.1 Add `scripts/test_world_narrative_ingestion.py` for compliance and ingest behavior.
- [ ] 6.2 Add `scripts/test_world_narrative_routes.py` for path guardrails, lock behavior, and fail-closed responses.
- [ ] 6.3 Run compile checks on modified/new Python files.
- [ ] 6.4 Manual smoke test toolkit workflow end-to-end.

## 7. Builder handoff

- [ ] 7.1 Update `openspec/changes/world-narrative-seed-bootstrap-and-toolkit-ingestion/executor_prompts.md` with step-ordered prompts and verification gates.
