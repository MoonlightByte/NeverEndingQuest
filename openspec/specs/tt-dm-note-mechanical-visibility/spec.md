## Purpose

Ensure DM Note mechanical summaries accurately reflect live character state for inventory (equipment, ammunition, currency) and limited-use resources (class feature usage), enabling the narrator to see and act on the same mechanical reality that Python persists.

## Requirements

### Requirement: DM Note mechanical summaries SHALL reflect the live character inventory schema

DM Note inventory visibility SHALL summarize current mechanical items from the live character schema rather than relying on deprecated `inventory.items`-only assumptions.

#### Scenario: Equipment-backed items appear in DM Note context
- **WHEN** a character carries items under top-level `equipment` or `ammunition`
- **THEN** DM Note mechanical summaries SHALL be able to surface those items in bounded form
- **AND** SHALL NOT omit them solely because `inventory.items` is absent

### Requirement: DM Note limited-resource visibility SHALL reflect nested feature usage

DM Note resource summaries SHALL recognize nested `classFeatures[].usage` objects for limited-use features.

#### Scenario: Rage usage appears from nested usage state
- **WHEN** a character feature such as `Rage` stores usage as `usage.current` and `usage.max`
- **THEN** DM Note mechanical summaries SHALL expose the current remaining use state in bounded form
- **AND** narrator/runtime context SHALL not rely only on prose memory for that feature state

### Requirement: DM Note visibility SHALL remain compact

Mechanical visibility hardening SHALL preserve concise DM Note output rather than dumping full sheets.

#### Scenario: Compact summary remains bounded
- **WHEN** DM Note rendering includes inventory or limited-resource summaries
- **THEN** those summaries SHALL remain compact and relevance-bounded
- **AND** unrelated mechanical detail SHALL remain omitted
