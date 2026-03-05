# module-validation-bulk-default-targeting

## Why

Module validation is not reliable enough for a workflow that ingests or downloads many modules:
- `core/validation/validate_module_files.py` is hardcoded to `modules/Keep_of_Doom` in `main()` and does not support selecting arbitrary modules from CLI.
- The validator requires `jsonschema` at import-time, which can fail before useful CLI guidance is shown.
- Strict ingest currently has a fail-open path when validator dependencies are unavailable.
- There is no single bulk command that validates all candidate modules with a sane default target set.

## What Changes

1. Add module-selectable CLI support to `core/validation/validate_module_files.py`.
2. Enforce strict ingest fail-closed behavior when schema validator dependencies are unavailable.
3. Add a bulk validation entrypoint that supports validating all candidate modules by default.
4. Align documentation and regression tests with the new contracts.

## Recommended Default Target Policy

When no explicit module list is provided, bulk validation SHOULD target:
- Modules registered in `modules/world_registry.json` (if folder exists), plus
- Any module-like folder under `modules/` that contains `areas/` with JSON files.

The default target resolver MUST exclude non-module/system directories (for example: `ingest`, `conversation_history`, `campaign_summaries`, `backups`, hidden folders).

## Capabilities

This change adds:
- `module-validator-cli-targeting`
- `module-bulk-validation-default-targeting`
- `strict-ingest-validator-availability-gate`

## Impact

- Facilitators can validate any specific module before use.
- Teams can run one bulk command to validate ingested and GitHub-downloaded modules.
- Strict ingest can no longer pass when validator dependencies are missing.
- Existing validation logic remains reusable through `ModuleValidator`.
