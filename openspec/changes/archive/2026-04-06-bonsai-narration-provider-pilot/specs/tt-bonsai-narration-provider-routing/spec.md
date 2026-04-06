## ADDED Requirements

### Requirement: Bonsai pilot routing SHALL be bounded to allowlisted narration tasks
When the Bonsai narration pilot is enabled, runtime SHALL route only explicitly allowlisted narration tasks to the Bonsai OpenAI-compatible endpoint.

#### Scenario: dm_main routes to Bonsai during pilot
- **WHEN** the Bonsai narration pilot is enabled
- **AND** the runtime prepares a `dm_main` narration request
- **THEN** the request SHALL use the Bonsai-configured OpenAI-compatible client and Bonsai model

#### Scenario: pilot disabled preserves existing narration provider
- **WHEN** the Bonsai narration pilot is disabled
- **AND** the runtime prepares a `dm_main` narration request
- **THEN** the request SHALL continue using the existing configured provider path

### Requirement: Bonsai routing SHALL use explicit local API configuration
The Bonsai narration pilot SHALL use explicit configuration for base URL, model identity, and API-key placeholder rather than reusing unrelated provider settings implicitly.

#### Scenario: explicit Bonsai configuration is used
- **WHEN** the runtime creates a Bonsai-routed narration client
- **THEN** it SHALL use the configured Bonsai base URL and Bonsai model
- **AND** it SHALL treat the API key as an OpenAI-compatible placeholder rather than a cloud credential
