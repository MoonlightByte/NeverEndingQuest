# homebrew-ingest-media-cost-guard Specification

## Purpose
TBD - created by archiving change homebrew-ingest-working-adventure-hardening. Update Purpose after archive.
## Requirements
### Requirement: Ingest media stages SHALL remain cost-safe by default

Homebrew ingest SHALL support media readiness without requiring paid provider image generation unless explicitly requested.

#### Scenario: Default run keeps provider generation disabled

- **WHEN** ingest runs without `--allow-provider`
- **THEN** portrait prewarm SHALL not call provider image generation APIs
- **AND** report SHALL state provider generation was not allowed

#### Scenario: URL media extraction remains non-provider path

- **WHEN** media extraction is enabled
- **THEN** media stage SHALL source assets from module markdown URLs and local file copies only
- **AND** failures SHALL be fail-open warnings unless explicitly configured otherwise

#### Scenario: Explicit provider opt-in is honored

- **WHEN** ingest runs with `--allow-provider`
- **THEN** prewarm stage MAY call provider image generation for missing portraits
- **AND** report SHALL explicitly indicate provider generation was allowed

