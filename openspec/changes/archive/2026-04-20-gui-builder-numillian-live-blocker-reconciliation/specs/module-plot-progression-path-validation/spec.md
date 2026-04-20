## ADDED Requirements

### Requirement: Deterministic plot repair SHALL target validator-identified failing conclusion edges

When validation identifies a missing prerequisite gate for a specific conclusion or finale plot point, deterministic repair SHALL target that failing edge directly.

#### Scenario: Validator identifies non-terminal conclusion node

- **WHEN** validation reports that `PP018` is missing an explicit prerequisite on `PP017`
- **AND** the numeric terminal node is a different plot point (for example `PP019`)
- **THEN** deterministic repair SHALL add the prerequisite to `PP018`
- **AND** SHALL NOT retarget the repair to the numerically last plot point
