## MODIFIED Requirements

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
