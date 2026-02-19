## ADDED Requirements

### Requirement: Portrait image identity and version metadata MUST be emitted for GUI refresh paths

Backend payloads used by Character Sheet, initiative queue, and party strip SHALL expose canonical image identity and deterministic version metadata for entities that can render portraits.

#### Scenario: Character Sheet stats payload includes portrait metadata
- **WHEN** client requests `player_data_response` with `dataType=stats`
- **THEN** payload includes `_portrait_slug` and `_portrait_version`

#### Scenario: Initiative payload includes image metadata
- **WHEN** client requests `initiative_data_response` during active combat
- **THEN** each player/NPC combatant entry includes `image_slug` and `image_version`

#### Scenario: Party payload includes image metadata
- **WHEN** client requests `party_data_response`
- **THEN** each party member and location NPC entry includes `image_slug` and `image_version`

### Requirement: Frontend portrait slug normalization MUST be consistent with backend filename normalization

All frontend portrait URL builders SHALL use one canonical slug normalization helper aligned with backend character filename normalization semantics.

#### Scenario: Name with apostrophe or punctuation
- **WHEN** an entity name includes apostrophes, spaces, or punctuation
- **THEN** Character Sheet, initiative, and party strip resolve the same normalized slug

### Requirement: Frontend portrait URLs SHALL be versioned for deterministic cache refresh

Portrait and thumbnail URLs rendered in GUI surfaces SHALL append deterministic version query values when metadata is available.

#### Scenario: Portrait file replaced in place
- **WHEN** a portrait file is overwritten with updated content
- **THEN** rendered URL changes due to version metadata and browser uses refreshed asset

### Requirement: Successful portrait mutation SHALL invalidate local image caches for affected identity

On successful upload/create mutation, frontend SHALL invalidate both known-existing and known-missing local image cache entries for the affected slug before rerender.

#### Scenario: Create success after prior miss cache
- **WHEN** portrait create succeeds for an entity that previously had missing-image cache entries
- **THEN** stale missing cache entries for that slug are cleared and refreshed image can render immediately

### Requirement: Successful portrait mutation SHALL trigger immediate cross-surface refresh

On successful upload/create mutation, GUI SHALL refresh Character Sheet, initiative, and party payloads immediately without waiting for polling interval.

#### Scenario: Upload success during active session
- **WHEN** user uploads a portrait
- **THEN** Character Sheet portrait, initiative portrait, and party strip portrait all refresh in same interaction window
- **AND** no update-then-revert behavior appears on subsequent poll cycles

### SHOULD Guidance

- Implement version metadata in a shared backend helper so all payload builders reuse identical logic.
- Keep frontend cache invalidation targeted by slug rather than clearing global image cache maps.
