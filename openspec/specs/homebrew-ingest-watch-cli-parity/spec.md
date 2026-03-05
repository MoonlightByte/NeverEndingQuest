# homebrew-ingest-watch-cli-parity Specification

## Purpose
TBD - created by archiving change homebrew-watcher-strict-cli-parity. Update Purpose after archive.
## Requirements
### Requirement: Watcher And CLI Pipeline Parity For Validated Markdown

For ingest-ready markdown, watcher ingest MUST use the same core pipeline stages and produce equivalent stage outcomes as CLI ingest.

#### Scenario: Shared pipeline execution for validated input
- WHEN the same validated markdown is processed by CLI and watcher
- THEN both flows execute the same core ingest stages
- AND both produce equivalent module slug and core stage success outcomes.

#### Scenario: Canonical sidecar stage keys
- WHEN watcher ingest completes
- THEN watcher sidecar `result` MUST include canonical stage blocks (`media_extraction`, `media_handles`, `portrait_prewarm`)
- AND these keys MUST align with sidecar audit expectations.

#### Scenario: Provider generation remains opt-in
- WHEN watcher ingests validated markdown under default settings
- THEN provider generation stages MUST NOT run paid generation by default
- AND provider-enabled behavior MUST require explicit opt-in configuration.

