## Context

Ingest-generated module folders are not automatically surfaced by toolkit APIs because module listing is registry-backed (`world_registry.json` via module stitcher). A module that validates but is not registered is effectively not playable from normal module-selection flows.

We need a deterministic ingestion contract that ends in registry presence, not just local JSON artifact creation.

## Goals / Non-Goals

**Goals:**

- Ensure strict ingest success implies registry integration success.
- Ensure watched markdown files use deterministic ingest path by default.
- Ensure sidecar audit clearly reports registration outcome.

**Non-Goals:**

- Full PDF ingest parser implementation.
- Registry schema redesign.
- Replacement of module stitcher safety checks.

## Architecture Decisions

1. **Post-validation registration gate (MUST)**
   - After strict validation passes, importer MUST call registry integration using `ModuleStitcher.integrate_module(module_slug)`.
   - If integration fails, importer returns `quarantined` with reason `registry_integration_failed`.

2. **Success contract hardening (MUST)**
   - `status=success` requires both:
     - schema validation pass
     - confirmed module presence in `world_registry.modules`

3. **Watcher deterministic default (MUST)**
   - `module_ingest_watch` MUST pass `use_deterministic=True` for watched markdown/text sources.
   - AI builder path remains available for explicit CLI/manual runs only.

4. **Audit traceability (MUST)**
   - Sidecar payload MUST include registration result object:
     - `registration_attempted`
     - `registration_success`
     - `registry_module_present`
     - `registration_errors`

5. **Failure behavior (MUST)**
   - Validation failure: quarantine, do not register.
   - Registration failure after validation pass: quarantine, archive, explicit reason in sidecar.

6. **Compatibility (SHOULD)**
   - Keep startup fail-open in web server.
   - Keep archive filename/status conventions unchanged.

## Risks / Trade-offs

- **Risk:** Stitcher integration can fail due to content safety or conflict checks.
  - **Mitigation:** quarantine with explicit error payload and no success state.

- **Risk:** Deterministic parser may produce sparse but valid modules.
  - **Mitigation:** treat as playable baseline; iterate quality via parser improvements.

- **Risk:** Registry write exceptions can produce partial state.
  - **Mitigation:** use existing stitcher integration path and verify registry presence post-call.

## Migration Plan

1. Implement importer registration helper and wire into strict success path.
2. Enforce watcher deterministic default for markdown/text ingest.
3. Extend result payload + sidecar fields with registration audit details.
4. Add/extend tests for registration success/failure contracts.
5. Run end-to-end smoke with Birble source and confirm toolkit visibility.

Rollback:

- Disable watcher via config.
- Keep importer returning quarantined on registration exceptions.
- Revert registration hook while retaining deterministic parser.

## Verification Strategy

- Compile checks:
  - `python3 -m py_compile core/importers/homebrewery_importer.py web/extensions/module_ingest_watch.py`
- Tests:
  - importer registration success/failure path tests
  - watcher deterministic default test
  - sidecar registration audit field tests
- Manual smoke:
  - drop Birble markdown into `modules/ingest/`
  - verify archive + sidecar + registry entry
  - verify module appears in `/api/toolkit/modules`
