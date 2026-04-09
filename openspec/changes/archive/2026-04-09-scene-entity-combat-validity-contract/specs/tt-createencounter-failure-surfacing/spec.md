## MODIFIED Requirements

### Requirement: createEncounter failure SHALL be explicit and non-misleading
When encounter generation fails because required monster stat files are missing, because a requested monster is not authorized by module-authored content, or because a requested target is an authored scene entity that is not combat-valid, the system SHALL provide actionable error feedback and SHALL NOT present misleading combat-start narration.

#### Scenario: Non-combat-valid scene entity rejection emits scene-specific system error
- **WHEN** `createEncounter` references a current-scene authored NPC marked as non-combat-valid scene content
- **THEN** action processing SHALL return `status:error`
- **AND** the error message SHALL identify the failure class as scene-only or otherwise non-combat-valid scene-entity content
- **AND** the error message SHALL NOT describe that entity only as a generic unauthorized monster reference
- **AND** chat history SHALL include a `[SYSTEM]` error message for operator visibility
