## MODIFIED Requirements

### Requirement: Create with DM SHALL finalize only schema-valid complete characters

The DM interview flow SHALL finalize character creation only after extracting a complete final JSON payload that passes schema validation and completeness audit, including authored `backstory`. Startup DM creation and mid-campaign `Create with DM` SHALL use the same shared finalization contract for JSON extraction, corrective guidance, and persistence outcomes.

#### Scenario: Valid final JSON from interview
- **WHEN** the LLM returns a final character JSON that satisfies schema and completeness requirements including `backstory`
- **THEN** the system saves the character, updates party state, and exits creation mode using the shared finalization contract

#### Scenario: Invalid or incomplete final JSON
- **WHEN** the LLM returns malformed JSON or missing required completeness fields (including `backstory`)
- **THEN** the system keeps creation mode active, emits corrective guidance with missing or invalid fields, and requests corrected final output using the shared finalization contract

#### Scenario: Code-fenced JSON final response
- **WHEN** the LLM returns final JSON in a fenced code block
- **THEN** the system extracts and validates the payload using the same shared finalization rules as raw JSON

### Requirement: Startup and mid-campaign DM creation SHALL share one canonical creation core

Startup DM creation and mid-campaign `Manage Party -> Create with DM` SHALL share a single canonical prompt/context and finalization core while preserving their adapter-specific runtime semantics.

#### Scenario: Startup keeps its existing interview behavior
- **WHEN** startup DM creation runs during onboarding
- **THEN** the startup wizard retains its existing interview loop, iterative onboarding, and bootstrap lifecycle behavior while using the shared creation core underneath

#### Scenario: Mid-campaign Create with DM keeps web creation-mode behavior
- **WHEN** `Manage Party -> Create with DM` runs during an ongoing campaign
- **THEN** the web flow retains conversation backup/restore, creation-mode pause/resume, target-level context, and web queue integration while using the shared creation core underneath

#### Scenario: Prompt drift does not reappear between startup and GUI DM creation
- **WHEN** startup and mid-campaign DM creation build their interview prompts
- **THEN** both flows use the same canonical field/output contract and differ only in explicit mode-specific context

### SHOULD Guidance
- SHOULD implement the canonical creation core in a neutral utility/service layer rather than inside startup-only or web-only modules.
- SHOULD reduce duplicate direct character-save logic so both adapters route through one persistence helper.
