## ADDED Requirements

### Requirement: Toolkit readiness provenance SHALL be source-aware
Readiness and publishability evaluation MUST distinguish toolkit-produced modules from watcher-ingested modules so each source is validated against the provenance artifacts that source actually emits.

#### Scenario: Toolkit build uses toolkit-native provenance
- **WHEN** readiness or publishability evaluation runs for a module with `source="toolkit"`
- **THEN** the evaluator MUST accept toolkit-native provenance artifacts
- **AND** MUST NOT require an ingest archive sidecar as the only valid provenance source

#### Scenario: Watcher build still requires ingest sidecar provenance
- **WHEN** readiness or publishability evaluation runs for a module with `source="watcher"`
- **THEN** the evaluator MUST require ingest-sidecar provenance
- **AND** MUST fail if the watcher-sidecar contract is missing or invalid

### Requirement: Provenance failures SHALL report source-contract diagnostics
When provenance validation fails, the evaluator MUST report which source contract was expected and which artifact class was missing or invalid.

#### Scenario: Toolkit provenance missing
- **WHEN** a toolkit build reaches readiness evaluation without toolkit-native provenance artifacts
- **THEN** the result MUST fail with an explicit toolkit provenance error
- **AND** MUST NOT collapse to a generic `sidecar_missing` error intended for watcher flows

#### Scenario: Watcher provenance missing
- **WHEN** a watcher build reaches readiness evaluation without a valid ingest sidecar
- **THEN** the result MUST fail with an explicit watcher provenance error
- **AND** MUST preserve the watcher-sidecar requirement semantics
