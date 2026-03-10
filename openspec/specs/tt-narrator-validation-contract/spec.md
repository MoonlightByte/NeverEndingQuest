## Purpose

Define authoritative validation behavior for off-location NPC arrival state synchronization so deterministic checks control arrival truth and LLM validation cannot override deterministic outcomes.
## Requirements
### Requirement: Deterministic validator is authoritative for arrival sync

Deterministic validation SHALL be the source of truth for off-location NPC arrival state sync checks.

#### Scenario: Off-location mention without action fails
- **WHEN** narration mentions an off-location NPC and no matching state action exists in the same response
- **THEN** deterministic validation SHALL fail with explicit required action

#### Scenario: Present NPC mention passes
- **WHEN** narration mentions an NPC already present at current location
- **THEN** deterministic validation SHALL pass without extra arrival action

### Requirement: LLM validator SHALL NOT re-litigate deterministic arrival results

LLM validation SHALL respect deterministic arrival verdicts and only evaluate non-arrival semantics.

#### Scenario: Deterministic pass respected
- **WHEN** deterministic metadata indicates `deterministic_passed = true`
- **THEN** LLM validation SHALL NOT fail on arrival-sync grounds

#### Scenario: Deterministic fail remains blocking
- **WHEN** deterministic metadata indicates `deterministic_passed = false`
- **THEN** response SHALL remain failed for deterministic reason
- **AND** LLM output SHALL NOT override to pass

### Requirement: Contradictory arrival guidance SHALL NOT be emitted

Validation payload assembly SHALL avoid contradictory rule blocks for arrival sync.

#### Scenario: Contradiction exclusion
- **WHEN** both "arrival sync required" and contradictory waiver guidance are candidates
- **THEN** contradictory waiver guidance SHALL be excluded

### Requirement: Party-member exemption and ambiguity fail-open are preserved

Existing exemptions and ambiguity policy SHALL remain stable.

#### Scenario: Party-member mention is exempt
- **WHEN** short-name mention maps to party member identity
- **THEN** arrival-sync failure SHALL NOT trigger

#### Scenario: Ambiguous alias mention fails open
- **WHEN** mention resolves to multiple NPC candidates
- **THEN** deterministic arrival validator SHALL fail open for ambiguity

### Requirement: Deterministic failure taxonomy is structured

Deterministic failures SHALL use consistent reason codes and structured export.

#### Scenario: Structured export shape
- **WHEN** deterministic result is exported to LLM validation context
- **THEN** shape SHALL be `{"passed": bool, "reason": str|null, "required_action": str|null}`

#### Scenario: Reason code set
- **WHEN** deterministic validator fails
- **THEN** reason SHALL be one of `off_location_arrival_missing_action`, `ambiguous_mention`, or `validation_error`

### Requirement: Deterministic Arrival Handoff SHALL Be Enforced in Python

Arrival-sync deterministic pass/fail SHALL be enforced by runtime logic, not only by prompt guidance.

#### Scenario: Deterministic pass with conflicting LLM arrival critique
- **WHEN** deterministic validation result is `deterministic_passed = true`
- **AND** LLM validation text includes arrival-sync failure language
- **THEN** runtime SHALL keep arrival-sync verdict as pass
- **AND** SHALL continue evaluating only non-arrival validation dimensions

#### Scenario: Deterministic fail remains blocking
- **WHEN** deterministic validation result is `deterministic_passed = false`
- **THEN** runtime SHALL fail validation with deterministic reason
- **AND** LLM validator output SHALL NOT override to pass

### Requirement: Travel Intent Classifier SHALL Use Phrase-Level Intent

Travel intent detection SHALL use phrase/verb intent checks and SHALL NOT rely on broad token substring matching.

#### Scenario: Non-travel utterance with generic token
- **WHEN** user utterance includes generic words such as `to`
- **AND** no travel intent phrase/verb exists
- **THEN** runtime SHALL classify `is_travel_intent = false`

#### Scenario: Valid travel utterance
- **WHEN** user utterance clearly expresses movement intent
- **THEN** runtime SHALL classify `is_travel_intent = true`
- **AND** fail-soft arrival handling MAY apply per existing explicit-arrival rules

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

