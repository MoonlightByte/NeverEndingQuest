## ADDED Requirements

### Requirement: Monster closure SHALL reconcile validator-visible structured monsters with authority filtering

Deterministic monster closure SHALL not fail solely because the same normalized identity also appears in module NPC catalogs when the validator-visible authored usage is an explicit structured monster reference.

#### Scenario: Structured monster reference shares identity with NPC catalog entry

- **WHEN** a module authors a slug in `locations[].monsters[]`
- **AND** the same slug also appears in an NPC catalog surface
- **THEN** deterministic monster closure SHALL still treat the structured monster evidence as eligible for reconciliation
- **AND** SHALL NOT fail with `unauthorized_monster_reference` solely due to the NPC catalog overlap

### Requirement: Monster schema completion SHALL use bounded canonical recovery

Deterministic schema completion SHALL attempt safe authoritative canonical recovery when a monster slug does not exactly match the compendium identity.

#### Scenario: Singular/plural recovery resolves authoritative source

- **WHEN** a module monster file is missing required schema fields
- **AND** exact compendium lookup for its slug fails
- **AND** a bounded canonical variant such as singular/plural recovery resolves to one authoritative source entry
- **THEN** schema completion SHALL backfill from that authoritative source
- **AND** SHALL report the recovery mode used
