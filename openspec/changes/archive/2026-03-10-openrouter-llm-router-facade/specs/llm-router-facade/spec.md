## ADDED Requirements

### Requirement: Unified Router Entrypoint
The system MUST provide a single internal facade entrypoint for chat-based LLM calls that accepts task/role context, normalized message payloads, and optional call overrides.

#### Scenario: Callsites use one API contract
- **WHEN** an internal module invokes LLM generation through the router
- **THEN** it SHALL call a single facade method (`llm.call`) rather than creating provider clients directly

### Requirement: Backward-Compatible Output Contract
The router MUST return response payloads compatible with existing callsite expectations so single-player and tabletop gameplay flows do not require behavior changes during phase 1 adoption.

#### Scenario: Existing OpenAI flow remains behavior-compatible
- **WHEN** provider configuration remains on OpenAI defaults
- **THEN** router-mediated calls SHALL preserve expected textual/structured response shape used by current callsites

### Requirement: Provider Error Classification and Outcome Policy
The router MUST classify provider failures into retryable transient errors and non-retryable hard-stop errors, and it MUST execute the configured fallback policy deterministically.

#### Scenario: Retryable provider failure
- **WHEN** a call encounters timeout, connection interruption, or retryable HTTP status (429/502/503/504)
- **THEN** the router SHALL run bounded retry/fallback handling and either return success from fallback provider or return a terminal error after limits are reached

#### Scenario: Hard-stop provider failure
- **WHEN** a call encounters invalid credentials, explicit billing/quota exhaustion across available providers, or malformed auth configuration
- **THEN** the router SHALL stop retrying, return a failure with clear error class, and emit observability counters for the terminal condition

### Requirement: No Mechanical State Mutation in Router Layer
The router MUST remain transport/orchestration-only and MUST NOT mutate gameplay state, combat state, or persisted JSON files.

#### Scenario: Router called during combat update flow
- **WHEN** combat or narration code uses router output to drive game actions
- **THEN** all state mutations SHALL remain in existing action handlers/managers and not in router internals

### Requirement: Router Availability Degradation Path
If router initialization or profile resolution fails, the system MUST provide a safe degradation path that preserves gameplay continuity with legacy invocation behavior for configured-compatible modes.

#### Scenario: Profile resolution error on startup
- **WHEN** router cannot resolve a valid profile for a configured task
- **THEN** the system SHALL fall back to legacy-compatible model selection/default provider behavior and log a categorized warning for operator visibility
