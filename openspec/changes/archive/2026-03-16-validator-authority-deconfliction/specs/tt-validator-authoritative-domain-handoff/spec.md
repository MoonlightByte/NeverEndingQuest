## ADDED Requirements

### Requirement: Narrator deterministic handoff SHALL be domain-scoped

The narrator validation pipeline SHALL export deterministic authority as a structured per-domain payload rather than a single flat pass/fail flag.

#### Scenario: Payload includes required v1 domains
- **WHEN** narrator validation assembles deterministic handoff metadata
- **THEN** the payload SHALL include `travel_state_sync`, `npc_state_sync`, and `mechanics_precheck`
- **AND** each domain SHALL expose `passed`, `authoritative`, `reconciled`, `mode`, `reason`, and `required_action`

#### Scenario: Payload includes summary block
- **WHEN** narrator validation assembles deterministic handoff metadata
- **THEN** the payload SHALL include a `summary` block
- **AND** `summary` SHALL expose `all_authoritative_domains_passed`, `authoritative_failures`, and `reconciled_domains`

### Requirement: Authoritative-passed domains SHALL be non-reviewable by LLM validation

If a deterministic domain is both authoritative and passed, LLM validation SHALL NOT veto the response solely on that domain.

#### Scenario: Travel domain already reconciled
- **GIVEN** `travel_state_sync.passed = true`
- **AND** `travel_state_sync.authoritative = true`
- **WHEN** the LLM validator objects only to missing travel state action plumbing for that response
- **THEN** runtime SHALL suppress that domain failure
- **AND** SHALL accept the response if no unreconciled failure remains

#### Scenario: NPC scene-presence domain already reconciled
- **GIVEN** `npc_state_sync.passed = true`
- **AND** `npc_state_sync.authoritative = true`
- **WHEN** the LLM validator objects only to missing NPC arrival movement plumbing for that response
- **THEN** runtime SHALL suppress that domain failure

### Requirement: Unreconciled domains SHALL remain blockable

Authoritative domain handoff SHALL NOT suppress unrelated unreconciled failures.

#### Scenario: Mixed-domain failure remains blocking
- **GIVEN** travel or NPC state-sync domain is authoritative and passed
- **AND** an unrelated semantic or action-structure failure remains
- **WHEN** runtime evaluates LLM validation output
- **THEN** runtime SHALL keep the response invalid
- **AND** SHALL block on the unreconciled failure

### Requirement: Deterministic authoritative failures SHALL remain blocking

If a deterministic authoritative domain fails, runtime SHALL keep that failure blocking.

#### Scenario: Travel deterministic fail remains blocking
- **WHEN** `travel_state_sync.passed = false`
- **THEN** runtime SHALL fail the response with deterministic reason
- **AND** LLM validation SHALL NOT override it to valid

#### Scenario: Mechanics deterministic fail remains blocking
- **WHEN** `mechanics_precheck.passed = false`
- **THEN** runtime SHALL fail the response with deterministic reason
- **AND** that failure SHALL NOT be suppressible by later LLM validation
