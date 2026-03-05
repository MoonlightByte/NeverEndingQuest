## Purpose

Define pre-session tabletop validation requirements so missing monster references do not trigger fail-closed combat loading during live gameplay.

## Requirements

### Requirement: Tabletop-mode monster loading MUST be prevalidated for referenced monsters
Because tabletop mode fail-closes on missing monster JSON, module content MUST be prevalidated before gameplay session launch.

#### Scenario: Pre-session validation for tabletop mode
- **WHEN** module gameplay audit is executed pre-session
- **THEN** there are zero blocking monster-resolution errors for active referenced monsters

### Requirement: Slug normalization MUST match runtime behavior
Monster filename resolution MUST use the same normalization contract as runtime lookup.

#### Scenario: Normalized filename mapping
- **WHEN** a monster reference contains punctuation or spacing variance
- **THEN** normalization maps to the exact filename expected by runtime lookup logic
