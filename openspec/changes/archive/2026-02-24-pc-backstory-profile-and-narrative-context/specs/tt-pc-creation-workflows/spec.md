## MODIFIED Requirements

### Requirement: Create with DM SHALL finalize only schema-valid complete characters
The DM interview flow SHALL finalize character creation only after extracting a complete final JSON payload that passes schema validation and completeness audit, including authored `backstory`.

#### Scenario: Valid final JSON from interview
- **WHEN** the LLM returns a final character JSON that satisfies schema and completeness requirements including `backstory`
- **THEN** the system saves the character, updates party state, and exits creation mode

#### Scenario: Invalid or incomplete final JSON
- **WHEN** the LLM returns malformed JSON or missing required completeness fields (including `backstory`)
- **THEN** the system keeps creation mode active, emits corrective guidance with missing/invalid fields, and requests corrected final output

### Requirement: Roll Your Own SHALL collect narrative history via backstory field
The manual creation workflow SHALL include a `backstory` input so authored narrative history is captured during PC creation.

#### Scenario: Manual sheet-aligned creation includes backstory
- **WHEN** the DM completes Roll Your Own form and submits
- **THEN** payload includes `backstory`, backend validates completeness, and persistence proceeds only on success

#### Scenario: Manual submission missing backstory
- **WHEN** Roll Your Own submission omits `backstory`
- **THEN** save is blocked with completeness errors and no partial character file is created
