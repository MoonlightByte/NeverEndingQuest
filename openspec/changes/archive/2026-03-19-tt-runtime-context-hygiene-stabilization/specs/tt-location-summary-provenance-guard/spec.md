## ADDED Requirements

### Requirement: Derived location-memory blocks SHALL carry explicit provenance
Derived location summaries and chronicles SHALL include machine-checkable provenance identifying the scene they describe.

#### Scenario: New location summary is created
- **WHEN** the runtime creates a derived `[SUMMARY OF EVENTS AT THIS LOCATION]` block or `=== LOCATION CHRONICLE ===` block
- **THEN** the block SHALL carry provenance including current module, area id, location id, and source kind
- **AND** that provenance SHALL be available to later runtime consumers without heuristic scene guessing

### Requirement: Live runtime reuse SHALL reject mismatched derived provenance
The runtime SHALL exclude derived location-memory blocks from live reuse when their provenance does not match the active scene.

#### Scenario: Preserved summary belongs to another location
- **WHEN** preserved conversation history contains a derived location summary or chronicle block
- **AND** that block's provenance does not match the active module and current location
- **THEN** the block SHALL be excluded from live narrator payload assembly
- **AND** the block SHALL be excluded from reconciliation input assembly

#### Scenario: Matching provenance remains reusable
- **WHEN** a derived location summary or chronicle block has provenance matching the active module and current location
- **THEN** the runtime MAY reuse it in the live scene context
- **AND** current-scene raw turns SHALL remain available alongside it
