# tt-character-update-ux-recovery Specification

## Purpose
TBD - created by archiving change tt-character-ops-runtime-recovery-and-target-normalization. Update Purpose after archive.
## Requirements
### Requirement: Recoverable character update failures SHALL not freeze gameplay
When `updateCharacterInfo` includes a mixed `changes + ops` payload and deterministic ops application fails for a recoverable reason, runtime SHALL continue the turn through a safe recovery path instead of surfacing an opaque generic character update freeze.

#### Scenario: Mixed payload degrades through prose fallback on recoverable ops failure
- **WHEN** a mixed `updateCharacterInfo` payload includes prose `changes` and a deterministic op fails for a recoverable alias, normalization, or shape reason
- **THEN** runtime SHALL apply the prose fallback path instead of hard-failing the turn
- **AND** the turn SHALL continue without a generic unknown character update error being emitted to the player

#### Scenario: Structured-only recoverable payload remains blocked without safe fallback
- **WHEN** a structured-only `updateCharacterInfo` payload has no prose `changes` fallback and deterministic application fails
- **THEN** runtime SHALL reject the update instead of pretending success
- **AND** it SHALL surface a specific user-safe failure message

### Requirement: Authoritative blocked character updates SHALL surface specific user-safe feedback
Character update failures that remain fail-closed SHALL surface concise user-safe error messages rather than opaque generic unknown-error text.

#### Scenario: Authoritative contradiction is reported specifically
- **WHEN** deterministic character ops are rejected for an authoritative contradiction such as resource underflow, overflow, or impossible removal
- **THEN** runtime SHALL emit a specific user-safe failure reason for the blocked update
- **AND** it SHALL avoid surfacing a generic `Unknown error in character update` message for that turn

### Requirement: Recovery routing SHALL remain observable for diagnostics
Recoverable degradation and authoritative blocking outcomes SHALL remain observable through deterministic routing markers or equivalent diagnostics.

#### Scenario: Recoverable fallback records degraded routing outcome
- **WHEN** runtime falls back from deterministic apply to prose recovery for a mixed payload
- **THEN** it SHALL record a deterministic degraded routing reason
- **AND** that reason SHALL be available to regression tests and diagnostics without changing player-facing narration success semantics

