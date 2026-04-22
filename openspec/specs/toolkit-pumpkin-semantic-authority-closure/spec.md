# toolkit-pumpkin-semantic-authority-closure Specification

## Purpose
TBD - created by archiving change module-publishability-bucket-a-quick-wins. Update Purpose after archive.
## Requirements
### Requirement: Pumpkin quick-win remediation SHALL restore semantic-authority payload completeness
`The_Pumpkin_Kings_Curse` remediation SHALL restore the semantic-authority payload expected by publication-time semantic tooling.

#### Scenario: Pumpkin is structurally ready but blocked only by missing semantic authority
- **GIVEN** `The_Pumpkin_Kings_Curse` reports `ready_status=pass`
- **AND** publishability fails because `module_context.json` lacks semantic-authority payload
- **WHEN** Bucket A remediation lands
- **THEN** the module SHALL emit the required semantic-authority payload
- **AND** SHALL be eligible for publishability rerun without introducing unrelated structural work.

### Requirement: Pumpkin quick-win verification SHALL remain publishability-focused
Pumpkin verification SHALL prove the semantic-authority closure changed the publishability outcome rather than silently bypassing the gate.

#### Scenario: Pumpkin reruns publishability after semantic-authority closure
- **GIVEN** Pumpkin semantic-authority closure has landed
- **WHEN** readiness and publishability audits are rerun
- **THEN** the results SHALL continue to report explicit `ready_status` and `publishable_status`
- **AND** any remaining blocker SHALL be surfaced explicitly if Pumpkin still does not pass.

