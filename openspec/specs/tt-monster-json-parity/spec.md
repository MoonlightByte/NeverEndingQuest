## Purpose

Ensure all active Pumpkin King's Curse monster references resolve to valid, schema-compliant module monster JSON files.

## Requirements

### Requirement: All referenced monsters MUST resolve to module monster JSON files
Every active monster reference in `modules/The_Pumpkin_Kings_Curse/areas/*.json` (excluding backup files) MUST resolve to a normalized monster JSON file in `modules/The_Pumpkin_Kings_Curse/monsters/`.

#### Scenario: Active area monster reference resolution
- **WHEN** a monster name is referenced in `locations[].monsters`
- **THEN** `monsters/<normalized_slug>.json` exists and parses successfully

### Requirement: Monster JSON files MUST satisfy schema requirements
Newly created monster files MUST include all required fields from `schemas/mon_schema.json`.

#### Scenario: Required field validation
- **WHEN** monster JSON files are validated
- **THEN** no required key omissions remain
