## ADDED Requirements

### Requirement: Location NPC Dedupe SHALL Use Canonical Equality
Party-strip location NPC filtering SHALL compare canonicalized names by equality, not substring containment.

#### Scenario: Distinct names remain distinct
- **WHEN** location NPC list contains `Ansel`
- **AND** party members or party NPCs contain `Anselara`
- **THEN** dedupe SHALL treat them as distinct entities
- **AND** `Ansel` SHALL remain render-eligible in location NPCs

#### Scenario: True duplicate suppressed
- **WHEN** location NPC and party entry resolve to the same canonical name
- **THEN** dedupe SHALL suppress duplicate location NPC entry
- **AND** payload SHALL not include duplicate render cards for one entity
