## Purpose

Define authoritative validation behavior for off-location NPC arrival state synchronization so deterministic checks control arrival truth and LLM validation cannot override deterministic outcomes.
## Requirements
### Requirement: Deterministic validator is authoritative for arrival sync

Off-location NPC mention SHALL require a state-sync action only when narration includes explicit physical-arrival semantics, except where deterministic scene-presence reconciliation safely normalizes current-scene presence.

#### Scenario: Deterministic scene-presence reconcile blocks LLM re-litigation
- **GIVEN** deterministic runtime classifies one NPC mention as safe scene presence eligible for reconciliation
- **WHEN** narrator validation executes
- **THEN** runtime SHALL preserve the deterministic reconcile result for that NPC-presence dimension
- **AND** LLM validation SHALL NOT reintroduce a missing-arrival failure solely because explicit movement plumbing was omitted

#### Scenario: Explicit join remains unreconciled by scene-presence path
- **GIVEN** narration crosses from scene presence into durable party-join semantics
- **WHEN** deterministic runtime evaluates the response
- **THEN** scene-presence reconciliation SHALL NOT bypass explicit party-membership requirements

### Requirement: LLM validator SHALL NOT re-litigate deterministic arrival results

LLM validation SHALL NOT reintroduce arrival-sync failure when deterministic arrival-sync pass condition is satisfied.

#### Scenario: Deterministic pass for non-explicit mention
- **GIVEN** deterministic validator marks arrival-sync pass for a non-explicit off-location mention
- **WHEN** LLM validation executes
- **THEN** runtime SHALL keep arrival-sync as pass
- **AND** SHALL evaluate only non-arrival semantic dimensions

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

### Requirement: Packet-enabled validation handoff SHALL consume authoritative packet truth
For domains enabled by this foundation slice, narrator validation assembly SHALL use authoritative state packet fields as the canonical truth handoff instead of reconstructing those truths independently from multiple ad hoc sources.

#### Scenario: Packet-enabled validation uses shared state surface
- **WHEN** narrator validation assembles current location, party roster, party NPC roster, or touched topology context for a packet-enabled turn
- **THEN** the assembly path SHALL consume those truths from the authoritative state packet
- **AND** it SHALL avoid rebuilding different values for the same overlapping truths from separate ad hoc sources

### Requirement: Packet handoff SHALL remain additive during migration
The packet-enabled validation handoff SHALL remain additive during this migration slice and SHALL NOT require immediate replacement of every legacy validation context source.

#### Scenario: Legacy context remains available outside packet-enabled domains
- **WHEN** validation still requires non-packet legacy context outside the domains covered by this change
- **THEN** runtime MAY include that additional context
- **AND** packet-enabled overlapping truths SHALL still come from the authoritative state packet

### Requirement: Travel-intent validation SHALL prefer reconciliation over rejection when movement is legal
For turns classified as travel intent, narrator validation SHALL prefer runtime reconciliation over missing-action rejection when narrated movement is legal, topology-safe, and safely resolvable.

#### Scenario: Legal narrated movement without explicit travel action
- **WHEN** a turn is classified as travel intent
- **AND** narrated movement is legal and safely resolvable
- **AND** explicit `transitionLocation` is missing
- **THEN** validation SHALL allow runtime travel reconciliation to proceed
- **AND** the turn SHALL NOT fail solely for missing explicit travel action

#### Scenario: Illegal travel remains blocking
- **WHEN** a turn is classified as travel intent
- **AND** narrated movement is topology-illegal or unsafe to resolve
- **THEN** validation SHALL continue to block the travel commit
- **AND** runtime SHALL NOT treat reconcile-first behavior as a bypass for impossible movement

#### Scenario: Ambiguous travel requests clarification instead of wrong commit
- **WHEN** a turn is classified as travel intent
- **AND** narrated movement cannot be resolved safely to one destination or one progress interpretation
- **THEN** validation SHALL preserve safe current truth or request clarification
- **AND** SHALL NOT require an arbitrary exact destination commit

