## MODIFIED Requirements

### Requirement: Repair apply SHALL require explicit confirm and preserve mechanics
The system SHALL apply repairs only after explicit DM confirmation and SHALL only update approved narrative fields.

#### Scenario: Confirm applies only whitelisted fields
- **WHEN** DM confirms a repair proposal
- **THEN** only these fields may be updated: `personality_traits`, `ideals`, `bonds`, `flaws`, `backstory`, `backgroundFeature.name`, `backgroundFeature.description`

#### Scenario: Mechanical fields remain unchanged
- **WHEN** a repair apply operation completes
- **THEN** mechanical fields (for example HP, AC, abilities, saves, spell slots, equipment mechanics) are unchanged from pre-apply state

### Requirement: Repair pipeline SHALL support deterministic fallback for backstory
Repair preview/apply SHALL provide deterministic fallback text when `backstory` is missing and LLM proposal is unavailable.

#### Scenario: Preview generation failure fallback includes backstory
- **WHEN** LLM proposal generation fails or times out for a character missing `backstory`
- **THEN** preview returns deterministic fallback text for `backstory` and continues flow
