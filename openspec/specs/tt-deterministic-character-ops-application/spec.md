## Purpose
Define deterministic Python-side application guarantees for supported `updateCharacterInfo.ops`, including combat death-save persistence updates.

## Requirements
### Requirement: Supported character ops SHALL be applied deterministically
When supported `ops` are present, runtime SHALL validate and apply them directly in Python, including combat death-save persistence updates.

#### Scenario: Supported ops applied directly
- **WHEN** `updateCharacterInfo` includes supported `ops`
- **THEN** runtime SHALL apply those ops without requiring freeform interpretation of the same mechanic

#### Scenario: Death-save failure op is applied directly
- **WHEN** combat resolves a failed death saving throw through `updateCharacterInfo`
- **THEN** runtime SHALL apply the supported death-save failure operation deterministically in Python
- **AND** the resulting persisted character state SHALL retain the updated death-save counters after schema validation

#### Scenario: Supported death-save ops do not silently fall back
- **WHEN** a supported deterministic death-save op is present in `updateCharacterInfo`
- **THEN** runtime SHALL NOT discard that op through silent purge or prose fallback
- **AND** any failure to apply the supported op SHALL surface as deterministic runtime error handling rather than pretending the update succeeded
