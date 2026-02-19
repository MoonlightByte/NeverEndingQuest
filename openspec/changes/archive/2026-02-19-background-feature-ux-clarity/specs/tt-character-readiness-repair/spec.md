## MODIFIED Requirements

### Requirement: Repair apply SHALL require explicit confirm and preserve mechanics
The system SHALL apply repairs only after explicit DM confirmation and SHALL only update approved narrative fields.

#### Scenario: Confirm applies only whitelisted fields
- **WHEN** DM confirms a repair proposal
- **THEN** only these fields may be updated: `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.name`, `backgroundFeature.description`

#### Scenario: Mechanical fields remain unchanged
- **WHEN** a repair apply operation completes
- **THEN** mechanical fields (for example HP, AC, abilities, saves, spell slots, equipment mechanics) are unchanged from pre-apply state

#### Scenario: Generic placeholder replacement in repair apply
- **WHEN** repair apply targets a generic placeholder value in `backgroundFeature.name` or `backgroundFeature.description`
- **THEN** repair writes only approved narrative replacement text and preserves all non-targeted fields
