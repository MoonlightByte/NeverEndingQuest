## ADDED Requirements

### Requirement: Ingest and activation SHALL block unresolved monster references

Strict ingest and module activation/copy workflows SHALL reject modules that fail monster reference integrity checks.

#### Scenario: Strict ingest quarantines unresolved references

- **WHEN** strict ingest validates a module with unresolved area/location monster references
- **THEN** ingest result SHALL be `quarantined`
- **AND** validation errors SHALL include unresolved-reference details
- **AND** module SHALL NOT be activated in the registry

#### Scenario: Activation preflight blocks copied module

- **WHEN** a module is copied/selected for campaign activation
- **AND** preflight validation detects unresolved monster references
- **THEN** activation SHALL be blocked
- **AND** chat/system output SHALL provide concise actionable failure summary

#### Scenario: Valid module remains activatable

- **WHEN** preflight validation has zero unresolved references
- **THEN** activation/copy flow SHALL proceed unchanged
- **AND** existing single-player and multi-player behavior SHALL remain unaffected
