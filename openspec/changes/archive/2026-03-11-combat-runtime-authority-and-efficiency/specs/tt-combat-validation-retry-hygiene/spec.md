## ADDED Requirements

### Requirement: Combat validation retry corrections SHALL remain validation-local
Combat validation correction notes and invalid-JSON retry instructions SHALL remain validation-local and SHALL NOT be persisted into combat conversation history as user turns.

#### Scenario: Invalid combat validation result retried without history pollution
- **WHEN** combat validation requests a retry because the validator returned invalid JSON or corrective feedback
- **THEN** the retry instruction SHALL remain available to the retry flow
- **AND** it SHALL NOT be appended to persistent combat conversation history as a user message

#### Scenario: Clean later rounds are not contaminated by prior correction notes
- **WHEN** a later combat turn is processed after one or more validation retries
- **THEN** the live combat conversation history SHALL exclude prior validation-only correction notes
- **AND** subsequent combat prompt payloads SHALL not inherit those notes as normal user-turn context
