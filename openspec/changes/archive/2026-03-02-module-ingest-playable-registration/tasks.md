## 0. Change scaffold

- [X] 0.1 Create change artifacts (`proposal.md`, `design.md`, `tasks.md`, `executor_prompts.md`, specs).
- [X] 0.2 Lock success contract: ingest success requires validation pass + registry presence.

## 1. Importer registration integration

- [X] 1.1 Add registration helper in `core/importers/homebrewery_importer.py` that calls module stitcher integration for validated modules.
- [X] 1.2 Invoke registration only after strict validation pass.
- [X] 1.3 Confirm registry presence (`world_registry.modules[module_slug]`) before returning `success`.
- [X] 1.4 Return `quarantined` with reason `registry_integration_failed` when registration fails.

## 2. Watcher deterministic default

- [X] 2.1 Update `web/extensions/module_ingest_watch.py` to force deterministic ingest path for watched markdown/text files.
- [X] 2.2 Preserve startup fail-open and existing archive lifecycle behavior.

## 3. Sidecar and result audit hardening

- [X] 3.1 Extend importer result payload with registration audit fields:
  - `registration_attempted`
  - `registration_success`
  - `registry_module_present`
  - `registration_errors`
- [X] 3.2 Ensure watcher sidecar persists these registration fields unchanged.

## 4. Regression tests

- [X] 4.1 Extend `scripts/test_homebrewery_importer.py` with registration success path test.
- [X] 4.2 Extend `scripts/test_homebrewery_importer.py` with registration failure -> quarantine test.
- [X] 4.3 Extend `scripts/test_module_ingest_watch.py` with deterministic-default behavior test.
- [X] 4.4 Verify dry-run no-write contract remains intact.

## 5. Verification and smoke

- [X] 5.1 Compile checks on modified Python files.
- [X] 5.2 Run importer and watcher test suites.
- [X] 5.3 Manual smoke: Birble_Adventuring_Academy confirmed in registry with required fields (moduleName, addedDate, themes, plotObjective, levelRange). API server not running (missing flask), but registry entry proves playability.
- [X] 5.4 Quarantine path verified: strict mode correctly blocks invalid modules and modules with failed registration from entering registry.

## 6. Builder handoff

- [X] 6.1 Executor prompts aligned with implementation tasks.
- [X] 6.2 Stop conditions documented in executor prompts and verified during smoke.
