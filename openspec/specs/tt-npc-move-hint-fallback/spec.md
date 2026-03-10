## Purpose

Define strict-first NPC movement lookup behavior with canonical alias-aware fallback that preserves fail-closed ambiguity handling and deterministic logging.
## Requirements
### Requirement: Strict hint-first lookup SHALL run before fallback

`moveBackgroundNPC` lookup SHALL first attempt exact hinted-location identity resolution.

#### Scenario: Strict hint match success
- **WHEN** hint location contains matching NPC identity
- **THEN** strict match SHALL be returned
- **AND** fallback SHALL NOT execute

#### Scenario: Strict hint miss
- **WHEN** hinted location has no matching NPC identity
- **THEN** fallback path MAY execute

### Requirement: Canonical fallback SHALL be alias-aware and unambiguous

Fallback SHALL resolve aliases/canonical identity and accept only one match.

#### Scenario: Stale hint unambiguous fallback success
- **WHEN** strict hint fails
- **AND** canonical resolver maps input to exactly one NPC across locations
- **THEN** fallback SHALL resolve and continue movement processing

#### Scenario: Ambiguous canonical match fails closed
- **WHEN** canonical resolver yields multiple candidates
- **THEN** fallback SHALL fail closed with explicit ambiguity error
- **AND** no NPC SHALL be moved

#### Scenario: No canonical match
- **WHEN** canonical resolver yields no candidate
- **THEN** fallback SHALL return not found behavior

### Requirement: Fail-closed behavior and API compatibility SHALL be preserved

Existing action contract and fail-closed semantics for unresolved NPC moves SHALL remain stable.

#### Scenario: API compatibility
- **WHEN** existing callers invoke `moveBackgroundNPC`
- **THEN** request/response contract SHALL remain backward compatible

#### Scenario: Unresolved NPC move
- **WHEN** strict and fallback lookup both fail
- **THEN** system SHALL return error and SHALL NOT move any NPC

### Requirement: Fallback usage SHALL be logged deterministically

Fallback success SHALL emit deterministic log metadata for operator analysis.

#### Scenario: Fallback log record
- **WHEN** fallback resolves stale hint to concrete location
- **THEN** log SHALL include `name`, `stale_hint`, `resolved_location`, and timestamp in `NPC_MOVE_FALLBACK` record

### Requirement: Fallback Identity Matching SHALL Be Canonical-Aware

When strict location-hint lookup fails, fallback identity matching SHALL use canonical alias-aware resolution.

#### Scenario: Short/full alias fallback success
- **WHEN** strict hint fails for NPC short name
- **AND** canonical resolver maps it unambiguously to one NPC record
- **THEN** fallback SHALL resolve to that canonical NPC
- **AND** movement processing SHALL continue

#### Scenario: Canonical ambiguity fails closed
- **WHEN** canonical resolver returns multiple candidates for fallback identity
- **THEN** fallback SHALL fail closed
- **AND** runtime SHALL return explicit ambiguity error without moving any NPC

### Requirement: Strict-First Contract SHALL Remain Intact

Canonical fallback SHALL NOT bypass strict hint matching order.

#### Scenario: Strict hint exact match present
- **WHEN** strict hint location contains exact NPC identity match
- **THEN** runtime SHALL return strict match
- **AND** canonical fallback SHALL NOT be invoked

