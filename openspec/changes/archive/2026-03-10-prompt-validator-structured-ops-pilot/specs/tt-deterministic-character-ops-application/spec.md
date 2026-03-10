## ADDED Requirements

### Requirement: Supported character ops SHALL be applied deterministically
When supported `ops` are present, runtime SHALL validate and apply them directly in Python.

#### Scenario: Supported ops applied directly
- **WHEN** `updateCharacterInfo` includes supported `ops`
- **THEN** runtime SHALL apply those ops without requiring freeform interpretation of the same mechanic

### Requirement: Legacy prose fallback SHALL remain available and measurable
When `ops` are absent or unsupported, the legacy prose path SHALL remain available and SHALL emit deterministic fallback usage markers.

#### Scenario: Prose fallback used
- **WHEN** the payload lacks supported `ops` but includes valid legacy `changes`
- **THEN** runtime SHALL continue through the compatibility path
- **AND** fallback usage SHALL be surfaced in deterministic telemetry or logs
