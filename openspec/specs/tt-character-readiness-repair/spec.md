## ADDED Requirements

### Requirement: Readiness warning UI SHALL offer a Repair action with preview
When a character sheet displays readiness warnings, the UI SHALL provide a `Repair` action that opens a preview of proposed field updates before any write occurs.

#### Scenario: Repair action appears only when warnings exist
- **WHEN** readiness audit returns one or more warnings for a character sheet
- **THEN** the UI displays a `Repair` button in the warning block

#### Scenario: Preview shows proposed updates
- **WHEN** the DM clicks `Repair`
- **THEN** the system fetches a repair proposal and shows field-by-field proposed values before confirmation

### Requirement: Repair apply SHALL require explicit confirm and preserve mechanics
The system SHALL apply repairs only after explicit DM confirmation and SHALL only update approved narrative fields.

#### Scenario: Confirm applies only whitelisted fields
- **WHEN** DM confirms a repair proposal
- **THEN** only these fields may be updated: `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.name`, `backgroundFeature.description`

#### Scenario: Generic placeholder replacement in repair apply
- **WHEN** repair apply targets a generic placeholder value in `backgroundFeature.name` or `backgroundFeature.description`
- **THEN** repair writes only approved narrative replacement text and preserves all non-targeted fields

#### Scenario: Mechanical fields remain unchanged
- **WHEN** a repair apply operation completes
- **THEN** mechanical fields (for example HP, AC, abilities, saves, spell slots, equipment mechanics) are unchanged from pre-apply state

### Requirement: Repair pipeline SHALL be audit-gated and non-chat
Repair operations SHALL run through audit validation and SHALL not emit chat narration messages.

#### Scenario: Preview generation failure fallback
- **WHEN** LLM proposal generation fails or times out
- **THEN** system returns deterministic fallback text for missing narrative fields and continues preview flow

#### Scenario: Apply blocked on post-patch audit failure
- **WHEN** patched character fails schema or completeness audit
- **THEN** save is rejected, original character file remains unchanged, and structured errors are returned

#### Scenario: No chat side effects
- **WHEN** repair preview or apply executes
- **THEN** no user-visible chat message is enqueued as part of the repair flow

### Requirement: Repair endpoint SHALL enforce cooldown and observability
Repair preview/apply endpoints SHALL enforce per-character cooldown and produce structured ASCII-safe logs for traceability.

#### Scenario: Cooldown active
- **WHEN** repeated repair requests arrive for the same character within cooldown window
- **THEN** endpoint returns rate-limited response with retry guidance

#### Scenario: Audit logs produced
- **WHEN** repair preview or apply runs
- **THEN** logs include character identifier, action type (preview/apply), outcome, and warning/error counts

### Requirement: Backward compatibility SHALL be preserved
The readiness repair addition SHALL be additive and SHALL not change behavior for characters already passing readiness.

#### Scenario: Ready character has no repair prompt
- **WHEN** readiness audit returns no warnings
- **THEN** `Repair` action is not shown and existing sheet behavior is unchanged

#### Scenario: Existing export behavior remains compatible
- **WHEN** PDF export is requested without using repair
- **THEN** current non-fatal readiness warning behavior remains unchanged
