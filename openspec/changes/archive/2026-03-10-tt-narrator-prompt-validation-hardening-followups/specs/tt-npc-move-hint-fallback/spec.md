## ADDED Requirements

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
