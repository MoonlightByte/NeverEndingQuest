## ADDED Requirements

### Requirement: Retry exhaustion SHALL emit player-visible fail-closed guidance

When validation retries exhaust, runtime SHALL emit an immediate player-visible system message while preserving fail-closed control flow.

#### Scenario: Retry exhaustion on live narrator turn
- **WHEN** the validation loop exhausts retries for a live narrator turn
- **THEN** the runtime SHALL emit a visible `[SYSTEM]` message to the active user interface in the same turn path
- **AND** the runtime SHALL remain fail-closed for the rejected turn

### Requirement: Player-facing retry exhaustion guidance SHALL remain non-technical

The player-facing retry exhaustion message SHALL provide actionable retry guidance without exposing detailed validator jargon.

#### Scenario: Deterministic validation reason exists during retry exhaustion
- **WHEN** the runtime has a detailed deterministic or validator rejection reason
- **THEN** the player-facing system message SHALL use concise non-technical guidance
- **AND** the detailed reason SHALL remain available in debug logging rather than the main play surface
