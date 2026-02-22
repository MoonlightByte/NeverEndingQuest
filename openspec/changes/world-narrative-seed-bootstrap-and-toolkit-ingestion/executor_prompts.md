## Builder Execution Prompts - world-narrative-seed-bootstrap-and-toolkit-ingestion

Use task order strictly. Do not implement outside current prompt scope.

## Execution Contract

- MUST preserve copyright firewall boundaries.
- MUST use `/user_uploads/text/` for raw source files only.
- MUST reject legacy `/user_uploads/` paths outside `/user_uploads/text/`.
- MUST fail-closed on compliance hits during ingest.
- MUST avoid destructive DB/schema operations.
- SHOULD keep host edits minimal and marked `# TABLETOP MODE:`.
- SHOULD follow `meta_source_rubric.md` for profile taxonomy and abstraction boundaries.
- SHOULD follow `profile_assignment_list.md` for ingest-wave ordering and profile selection.

---

## Prompt 1 - Seed bootstrap and migration (tasks 1.x)

Implement tasks 1.1-1.4.

Scope:
- `core/memory/memory_db.py`
- `core/memory/__init__.py`

Requirements:
- Add seed bootstrap helper.
- Ensure additive migration coverage for world-model tables.
- Keep initialization backward compatible when seed is absent.

Verify:
- `python3 -m py_compile core/memory/memory_db.py core/memory/__init__.py`
- run idempotent init/migration smoke twice

---

## Prompt 2 - Source-anonymous ingest service (tasks 2.x)

Implement tasks 2.1-2.4.

Scope:
- `core/memory/world_narrative_ingest.py`

Requirements:
- Implement banned key/term detection.
- Implement fail-closed compliance validator.
- Implement profile/atoms/statistics ingest logic.

Verify:
- `python3 -m py_compile core/memory/world_narrative_ingest.py`
- run targeted unit tests for pass/fail payloads

---

## Prompt 3 - Toolkit API routes and registration (tasks 3.x, 5.x)

Implement tasks 3.1-3.4 and 5.1-5.2.

Scope:
- `web/routes/world_narrative_routes.py`
- `web/web_interface.py`

Requirements:
- Add upload/extract/build/ingest/job-status routes.
- Enforce upload path/type guards and one-active-job lock.
- Register routes and startup bootstrap call sequence.

Verify:
- `python3 -m py_compile web/routes/world_narrative_routes.py web/web_interface.py`
- route smoke for 400/409/success paths

---

## Prompt 4 - Toolkit panel integration (tasks 4.x)

Implement tasks 4.1-4.3.

Scope:
- `web/templates/module_toolkit.html`

Requirements:
- Add World Narrative Sources panel and attestation gate.
- Add JS flow for upload -> extract -> build -> ingest -> job status.
- Keep existing toolkit tabs functional.

Verify:
- manual toolkit panel smoke
- no console JS errors in panel workflow

---

## Prompt 5 - Tests and final verification (tasks 6.x, 7.x)

Implement tasks 6.1-6.4 and 7.1.

Scope:
- `scripts/test_world_narrative_ingestion.py`
- `scripts/test_world_narrative_routes.py`
- `openspec/changes/world-narrative-seed-bootstrap-and-toolkit-ingestion/executor_prompts.md`

Required final checks:
- compile checks for all changed Python files
- run both new test scripts
- manual end-to-end toolkit smoke
