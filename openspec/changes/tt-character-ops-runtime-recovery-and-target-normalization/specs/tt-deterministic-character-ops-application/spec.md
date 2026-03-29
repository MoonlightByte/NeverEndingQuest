## MODIFIED Requirements

### Requirement: Supported character ops SHALL be applied deterministically
When supported `ops` are present, runtime SHALL validate and apply them directly in Python, including combat death-save persistence updates. Runtime SHALL distinguish recoverable deterministic apply failures from authoritative invalid-state contradictions instead of treating all apply-time failures as equivalent.

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

#### Scenario: Recoverable deterministic apply failure degrades when prose fallback exists
- **WHEN** a mixed `changes + ops` payload includes a supported deterministic op that fails only for a recoverable normalization or non-authoritative shape reason
- **THEN** runtime SHALL degrade to the prose `changes` path instead of hard-failing the turn
- **AND** it SHALL record that deterministic application degraded rather than succeeded

#### Scenario: Authoritative contradiction remains fail-closed
- **WHEN** a supported deterministic op would produce an authoritative contradiction such as underflow, overflow, impossible removal, or an invalid death-save mutation
- **THEN** runtime SHALL fail closed for that update
- **AND** it SHALL NOT degrade that contradiction through prose fallback merely because `changes` text is also present
