## MODIFIED Requirements

### Requirement: Strict hint-first lookup SHALL run before fallback
`moveBackgroundNPC` lookup SHALL first attempt exact hinted-location identity resolution across both visible NPC records and hidden or revealable authored identities at that location.

#### Scenario: Strict hint match success
- **WHEN** hint location contains matching NPC identity
- **THEN** strict match SHALL be returned
- **AND** fallback SHALL NOT execute

#### Scenario: Hidden authored NPC matches hinted location
- **WHEN** hint location omits the NPC from visible `npcs` records
- **AND** authored investigation hooks at that location expose one matching hidden identity
- **THEN** strict lookup SHALL treat that identity as present at the hinted location
- **AND** movement processing SHALL continue without fallback

#### Scenario: Strict hint miss
- **WHEN** hinted location has no matching NPC identity in visible or hidden authored records
- **THEN** fallback MAY execute

### Requirement: Canonical fallback SHALL be alias-aware and unambiguous
Fallback SHALL resolve aliases/canonical identity against the full authored location NPC set, including hidden or revealable authored identities, and accept only one match.

#### Scenario: Stale hint unambiguous fallback success
- **WHEN** strict hint fails
- **AND** canonical resolver maps input to exactly one NPC across visible and hidden authored location records
- **THEN** fallback SHALL resolve and continue movement processing

#### Scenario: Ambiguous canonical match fails closed
- **WHEN** canonical resolver yields multiple candidates
- **THEN** fallback SHALL fail closed with explicit ambiguity error
- **AND** no NPC SHALL be moved

#### Scenario: No canonical match
- **WHEN** canonical resolver yields no candidate
- **THEN** fallback SHALL return not found behavior
