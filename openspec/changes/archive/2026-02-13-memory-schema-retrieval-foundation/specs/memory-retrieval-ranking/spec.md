## ADDED Requirements

### Requirement: Timeline retrieval SHALL be deterministic and ranked
The system SHALL provide `get_entity_timeline` retrieval that returns results in deterministic ranked order using explicit scoring factors.

#### Scenario: Stable repeated retrieval output
- **WHEN** the same timeline query is executed repeatedly with unchanged data
- **THEN** the returned event ordering is identical across runs

### Requirement: Retrieval scoring MUST prioritize high-signal memory over ambient noise
The retrieval score MUST include pinned state, active-PC relevance, importance, persistence class, decay behavior, and reinforcement to prioritize major memories over low-value recency noise.

#### Scenario: Old pinned core event outranks recent ambient event
- **WHEN** one candidate is pinned identity-core and another is recent ambient with low importance
- **THEN** the pinned identity-core event is ranked above the ambient event

### Requirement: Prompt-mode retrieval MUST remain bounded by item and token constraints
The retrieval layer MUST enforce top-K limits and support token-cap aware packaging so narrator prompts stay within bounded context budgets.

#### Scenario: Top-K cap enforced
- **WHEN** a retrieval request specifies a limit smaller than total eligible events
- **THEN** the result count does not exceed the requested limit
