## ADDED Requirements

### Requirement: Live narrator runtime SHALL use compressed prompt authority
Live narrator runtime SHALL load `prompts/system_prompt_compressed.txt` as the canonical system prompt.

#### Scenario: Runtime narrator prompt source
- **WHEN** the main gameplay loop initializes narrator prompt text
- **THEN** it SHALL load `prompts/system_prompt_compressed.txt`
- **AND** it SHALL NOT load `prompts/system_prompt.txt` for live narrator behavior

### Requirement: Conversation history prompt identity SHALL match compressed runtime source
Conversation-history maintenance SHALL identify the primary system prompt using the compressed narrator prompt.

#### Scenario: Prompt identity source
- **WHEN** conversation history updates need to identify the main system prompt
- **THEN** they SHALL use the compressed narrator prompt text as the identity source
