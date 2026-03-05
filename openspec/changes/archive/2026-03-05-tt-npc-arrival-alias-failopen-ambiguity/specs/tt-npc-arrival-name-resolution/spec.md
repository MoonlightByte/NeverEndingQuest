## ADDED Requirements

### Requirement: NPC Arrival Sync SHALL Resolve Unambiguous Short/Full Name Aliases

NPC arrival state sync validation SHALL treat unambiguous short and full name variants as the same NPC identity across narration mentions, present-state checks, and arrival action checks.

#### Scenario: Short mention with full-name arrival action

- **WHEN** narration mentions `oswin` and the NPC is not currently present
- **AND** actions include `moveBackgroundNPC` for `Oswin Peverell`
- **THEN** validation SHALL pass alias identity matching

#### Scenario: Short mention already present via full-name state

- **WHEN** narration mentions `amanita`
- **AND** current location or party NPC state already includes `Amanita Gorse`
- **THEN** validation SHALL treat the NPC as present
- **AND** SHALL NOT require an additional arrival action

### Requirement: Ambiguous NPC Alias Mentions SHALL Fail Open

When a short NPC alias maps to multiple possible identities, validation SHALL NOT hard-fail solely on that ambiguous mapping.

#### Scenario: Ambiguous short alias

- **WHEN** narration mentions `oswin`
- **AND** candidate identities include multiple distinct NPCs matching `oswin`
- **THEN** validation SHALL classify the alias as ambiguous
- **AND** SHALL NOT add that mention to hard-fail missing-arrival errors by itself

### Requirement: Unambiguous Missing Arrivals SHALL Still Fail Closed

Alias-aware behavior SHALL NOT weaken fail-closed guarantees for true unambiguous off-location NPC mentions.

#### Scenario: Missing action for unambiguous off-location NPC

- **WHEN** narration mentions an unambiguous NPC not currently present
- **AND** no matching `moveBackgroundNPC` or `updatePartyNPCs` `add` action exists
- **THEN** validation SHALL fail with missing-arrival reason text

### Requirement: Party Member Exemption SHALL Remain Intact

Party members SHALL remain exempt from NPC arrival state sync enforcement even if module NPC names overlap.

#### Scenario: Party member name collision

- **WHEN** narration mentions a name shared by a party member and module NPC data
- **THEN** validation SHALL preserve party member exemption behavior
- **AND** SHALL NOT require NPC arrival action solely due to that mention
