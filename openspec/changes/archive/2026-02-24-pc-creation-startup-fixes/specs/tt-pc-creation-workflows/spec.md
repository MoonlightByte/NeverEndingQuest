## MODIFIED Requirements

### Requirement: Startup multi-PC onboarding SHALL require explicit facilitator confirmation
The startup wizard SHALL continue additional-PC onboarding until the facilitator explicitly confirms `no`.

#### Scenario: Add-more prompt is visible in web startup flow
- **WHEN** first PC creation succeeds during startup in web mode
- **THEN** the add-more question is emitted as line-visible output before input collection

#### Scenario: Blank input reprompts
- **WHEN** add-more decision input is blank (including timeout-injected blank)
- **THEN** startup SHALL reprompt and SHALL NOT advance to gameplay

#### Scenario: Invalid input reprompts
- **WHEN** facilitator enters non-yes/no text
- **THEN** startup SHALL show valid options and reprompt

#### Scenario: Explicit no exits loop
- **WHEN** facilitator enters `n` or `no`
- **THEN** startup exits additional-PC loop and proceeds to party tracker finalization

### SHOULD Guidance
- SHOULD accept canonical yes/no aliases only (`y/yes`, `n/no`) to keep behavior deterministic.
- SHOULD keep prompts concise for facilitator pacing in tabletop sessions.
