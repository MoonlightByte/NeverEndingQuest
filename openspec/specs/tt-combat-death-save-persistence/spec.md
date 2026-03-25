## Purpose

Define durable death-save turn handling and persistence guarantees for incapacitated player characters in multi-PC combat.

## Requirements

### Requirement: Incapacitated Active PCs SHALL Enter Death-Save-Only Turn Flow
When the active player character is at 0 HP and mechanically unconscious during combat, runtime MUST treat that turn as a death-save turn and MUST NOT accept ordinary attack or damage commands for that actor.

#### Scenario: Unconscious active PC is prompted for a death save
- **WHEN** combat turn ownership reaches an active PC whose authoritative mechanical state is 0 HP and unconscious
- **THEN** the required-response contract SHALL request a death saving throw before any other action resolution
- **AND** the response SHALL stop after issuing the death-save request

#### Scenario: Unconscious active PC attempts an attack command
- **WHEN** an active PC at 0 HP and unconscious submits `/att` or `/dmg`
- **THEN** runtime SHALL reject the command as invalid for that turn state
- **AND** the command SHALL NOT mutate encounter HP, target selection, or narration as if the PC acted normally

### Requirement: Death-Save Outcomes SHALL Persist Across Validation and Resume
Death-save successes and failures MUST survive character update processing, schema validation, and combat crash/resume recovery without being silently purged.

#### Scenario: Failed death save is committed
- **WHEN** combat resolves a death saving throw below the success threshold
- **THEN** the acting character SHALL persist one additional death-save failure in durable character state
- **AND** subsequent combat prompts SHALL reflect the updated failure count as authoritative truth

#### Scenario: Resumed combat preserves prior death-save counters
- **WHEN** combat resumes after interruption or crash for a character with existing death-save progress
- **THEN** the restored combat state SHALL preserve the previously committed death-save successes and failures
- **AND** the next death-save request SHALL continue from those counters instead of resetting to zero
