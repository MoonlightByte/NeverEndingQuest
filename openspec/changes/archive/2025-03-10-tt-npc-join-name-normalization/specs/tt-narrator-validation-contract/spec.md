## ADDED Requirements

### Requirement: Validation pipeline SHALL preprocess party-NPC action names before LLM validation

Narrator validation assembly SHALL apply deterministic canonical-name preprocessing to party-NPC action payloads before evaluating LLM full-name constraints.

#### Scenario: Deterministic preprocess prevents false full-name rejection
- **WHEN** action payload uses short NPC name that resolves unambiguously to a canonical name
- **AND** downstream LLM validation enforces full-name usage
- **THEN** runtime SHALL send canonicalized payload to LLM validator
- **AND** SHALL avoid rejection caused only by short-name form

#### Scenario: Preprocess failure remains blocking
- **WHEN** canonical-name preprocessing cannot resolve an action payload name safely
- **THEN** runtime SHALL fail validation with deterministic reason
- **AND** SHALL NOT defer unsafe resolution to LLM validator

### Requirement: Prompt and validator contract SHALL remain non-contradictory for canonical names

Validation and system prompt examples SHALL not contradict runtime canonical-name expectations for party-NPC action payloads.

#### Scenario: Canonical action example parity
- **WHEN** prompt examples describe `updatePartyNPCs` join behavior
- **THEN** examples SHALL use canonical NPC action names or explicit canonicalization guidance
- **AND** SHALL NOT present short-name action examples that conflict with full-name validation rules
