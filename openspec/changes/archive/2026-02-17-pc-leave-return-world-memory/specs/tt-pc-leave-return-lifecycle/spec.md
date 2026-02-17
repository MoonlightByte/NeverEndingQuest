## ADDED Requirements

### Requirement: Retirement API SHALL support optional departure text and graceful fallback narrative mode
The retirement endpoint MUST accept an optional departure text field and MUST support two narrative modes: explicit farewell when text is provided, and mysterious departure when text is blank.

#### Scenario: Retirement with explicit farewell text
- **WHEN** a retire request includes `character` and non-empty `departure_text`
- **THEN** the system processes retirement and prepares narration context that includes the provided farewell text

#### Scenario: Retirement with no farewell text
- **WHEN** a retire request includes `character` and empty or missing `departure_text`
- **THEN** the system processes retirement and prepares narration context using mysterious departure style

### Requirement: Retirement workflow MUST enforce runtime safety guards
The system MUST reject retirement requests during active combat and MUST reject retirement of the final remaining party member.

#### Scenario: Retirement blocked during active combat
- **WHEN** `worldConditions.activeCombatEncounter` is non-empty and a retire request is received
- **THEN** the request is rejected and no party membership mutation is committed

#### Scenario: Retirement blocked for last PC
- **WHEN** party membership count is one and that member is requested for retirement
- **THEN** the request is rejected and the final PC remains in `partyMembers`

### Requirement: Retirement and return workflows SHALL enqueue narration output
On successful retirement and successful return, the system SHALL enqueue a DM narration prompt that can include witness reactions for continuity.

#### Scenario: Retirement narration queued
- **WHEN** a valid retirement request succeeds
- **THEN** one retirement narration prompt is enqueued to the user input pipeline

#### Scenario: Return narration queued
- **WHEN** a valid add-existing return request succeeds
- **THEN** one return narration prompt is enqueued to the user input pipeline

### Requirement: Return workflow MUST retrieve continuity context before rejoin narration
The rejoin path MUST build a bounded memory context package from transition and social memory relevant to the returning entity before constructing return narration.

#### Scenario: Return memory context built from long-term memory
- **WHEN** a retired character is re-added to party membership
- **THEN** return narration context includes bounded transition and relationship memory snippets tied to that character

### Requirement: Leave and return operations MUST fail open for gameplay continuity
If lifecycle memory persistence fails, party add/remove operations MUST still complete while emitting degraded-mode logs and fallback narration context.

#### Scenario: Memory write failure during retirement
- **WHEN** retirement memory persistence fails due to DB unavailability
- **THEN** character removal from `partyMembers` still succeeds and fallback retirement narration is queued

#### Scenario: Memory write failure during return
- **WHEN** return memory persistence fails due to DB unavailability
- **THEN** character addition to `partyMembers` still succeeds and fallback return narration is queued
