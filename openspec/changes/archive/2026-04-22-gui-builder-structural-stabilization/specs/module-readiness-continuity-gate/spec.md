## ADDED Requirements

### Requirement: Readiness provenance validation SHALL be source-aware
Module readiness validation MUST evaluate provenance requirements according to the build source so toolkit-produced modules and watcher-produced modules are not forced through the same artifact contract.

#### Scenario: Toolkit source bypasses watcher-sidecar requirement
- **WHEN** `audit_module_readiness(...)` runs for a module declared with `source="toolkit"`
- **THEN** the readiness result MUST skip watcher-sidecar enforcement
- **AND** MUST evaluate toolkit-native provenance instead

#### Scenario: Watcher source preserves sidecar requirement
- **WHEN** `audit_module_readiness(...)` runs for a module declared with `source="watcher"`
- **THEN** the readiness result MUST continue to enforce watcher-sidecar success requirements
- **AND** MUST fail if the ingest-sidecar artifact is missing or invalid

#### Scenario: Unknown source fails closed
- **WHEN** readiness evaluation receives an unknown or unsupported build source
- **THEN** the evaluation MUST fail closed
- **AND** MUST report an explicit unsupported-source diagnostic
