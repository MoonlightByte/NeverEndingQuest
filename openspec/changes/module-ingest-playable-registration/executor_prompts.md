## Builder Execution Prompts - module-ingest-playable-registration

## Execution Contract

- MUST treat ingest success as `validation + registry presence`.
- MUST quarantine on registration failure after validation pass.
- MUST default watcher markdown/text ingest to deterministic path.
- MUST preserve startup fail-open and archive sidecar behavior.
- SHOULD use `ModuleStitcher.integrate_module()` as canonical registration path.
- SHOULD keep changes additive and merge-safe.

## Prompt 1 - Implement importer registration gate (tasks 1.1-1.4)

Scope:

- `core/importers/homebrewery_importer.py`

Requirements:

- Add helper that attempts module registration after strict validation pass.
- Use module stitcher integration path and confirm registry presence.
- Add fail-closed quarantine result when registration fails.
- Include registration audit fields in importer result payload.

Verify:

- `python3 -m py_compile core/importers/homebrewery_importer.py`
- Unit test registration success/failure paths (or temporary local harness).

Stop conditions:

- Stop if importer returns `success` without registry presence.
- Stop if registration exception path reports `success`.

## Prompt 2 - Enforce watcher deterministic default (tasks 2.1-2.2)

Scope:

- `web/extensions/module_ingest_watch.py`

Requirements:

- Ensure watched `.md/.markdown/.txt` files call importer with deterministic mode enabled.
- Preserve current archive move + sidecar behavior.
- Preserve startup fail-open behavior and worker lifecycle semantics.

Verify:

- `python3 -m py_compile web/extensions/module_ingest_watch.py`
- Existing worker tests still pass.

Stop conditions:

- Stop if watcher path can still invoke AI builder for watched markdown files.

## Prompt 3 - Sidecar audit field propagation (tasks 3.1-3.2)

Scope:

- `core/importers/homebrewery_importer.py`
- `web/extensions/module_ingest_watch.py`

Requirements:

- Ensure result payload contains registration audit fields.
- Ensure sidecar writes these fields without dropping keys.

Verify:

- Manual check of archive `.result.json` contains registration audit block.

Stop conditions:

- Stop if sidecar omits registration outcome fields.

## Prompt 4 - Tests and regressions (tasks 4.1-4.4)

Scope:

- `scripts/test_homebrewery_importer.py`
- `scripts/test_module_ingest_watch.py`

Requirements:

- Add importer tests for:
  - registration success -> status success
  - registration failure -> status quarantined + reason
- Add watcher test asserting deterministic-default call path.
- Re-assert dry-run no-write behavior.

Verify:

- `python3 -m py_compile scripts/test_homebrewery_importer.py scripts/test_module_ingest_watch.py`
- `python3 scripts/test_homebrewery_importer.py`
- `python3 scripts/test_module_ingest_watch.py`

Stop conditions:

- Stop if tests are flaky or dry-run writes artifacts.

## Prompt 5 - End-to-end smoke for playability (tasks 5.x, 6.x)

Scope:

- Full ingest + registry + API visibility flow
- `openspec/changes/module-ingest-playable-registration/tasks.md`

Requirements:

- Drop Birble markdown into `modules/ingest/`.
- Confirm archive + sidecar success.
- Confirm registry entry appears in `modules/world_registry.json`.
- Confirm module appears via toolkit API (`/api/toolkit/modules`).
- Confirm quarantine path still blocks registry write for invalid source.
- Update tasks checklist to completed for fulfilled items.

Verify:

- `python3 -m py_compile core/importers/homebrewery_importer.py web/extensions/module_ingest_watch.py scripts/import_homebrewery_module.py`
- `python3 scripts/test_homebrewery_importer.py`
- `python3 scripts/test_module_ingest_watch.py`
- Manual server smoke (`python3 run_web.py` + drop file)
- `git status --short`

Stop conditions:

- Stop if module is not in registry after success.
- Stop if invalid ingest still writes registry entry.
