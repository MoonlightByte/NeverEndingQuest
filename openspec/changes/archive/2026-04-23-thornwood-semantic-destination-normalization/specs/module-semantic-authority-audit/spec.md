## ADDED Requirements

### Requirement: Deterministic Thornwood Short-Form Destination Resolution

The Thornwood module semantic authority payload SHALL resolve the authored short-form destination phrase `north tower` to the same canonical location as `north tower overlook`.

#### Scenario: Thornwood short-form destination resolves to RO06

- **GIVEN** `The_Thornwood_Watch` semantic authority payload contains `north tower overlook` resolved to `RO06`
- **WHEN** the module semantic authority audit evaluates Thornwood destination phrases
- **THEN** `north tower` SHALL also resolve to `RO06`
- **AND** `north tower` SHALL NOT appear in `unresolved_destination_phrases`

### Requirement: Thornwood NPC Scene Authority Reflects Authored Placement

The Thornwood semantic authority payload SHALL not flag `Merchant Lira` as missing scene authority when the module already places her at `TW06`.

#### Scenario: Merchant Lira inherits visible location authority from authored placement

- **GIVEN** `module_context.json` places `Merchant Lira` in `TW06`
- **WHEN** the Thornwood semantic authority payload is evaluated
- **THEN** `Merchant Lira.visible_location_ids` SHALL include `TW06`
- **AND** `Merchant Lira` SHALL NOT appear in `missing_npc_authority`
